#!/usr/bin/env bash
# First-time setup of a fresh Ubuntu 24.04 EC2 instance. Run as root:
#   curl -fsSL https://raw.githubusercontent.com/LeifABOUTIN/GMhtml/memorials/server/deploy/setup.sh | sudo bash
# or, after cloning: sudo bash server/deploy/setup.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/LeifABOUTIN/GMhtml.git}"
BRANCH="${BRANCH:-memorials}"

apt-get update
apt-get install -y nginx python3-venv sqlite3 rsync git certbot python3-certbot-nginx
snap install aws-cli --classic || true

id gm &>/dev/null || useradd --system --home /srv/gm --shell /usr/sbin/nologin --gid www-data gm
mkdir -p /srv/gm/data/{media,static,cache,backups} /srv/gm/www
[ -d /srv/gm/repo/.git ] || git clone --branch "$BRANCH" "$REPO_URL" /srv/gm/repo
[ -d /srv/gm/venv ] || python3 -m venv /srv/gm/venv

if [ ! -f /srv/gm/env ]; then
	cp /srv/gm/repo/server/.env.example /srv/gm/env
	SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
	sed -i \
		-e "s|^DJANGO_DEBUG=.*|DJANGO_DEBUG=0|" \
		-e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$SECRET|" \
		-e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=gmfuneraire.fr,www.gmfuneraire.fr|" \
		-e "s|^SITE_URL=.*|SITE_URL=https://gmfuneraire.fr|" \
		-e "s|^#DJANGO_DATA_DIR=.*|DJANGO_DATA_DIR=/srv/gm/data|" \
		/srv/gm/env
	echo ">>> Edit /srv/gm/env (Google + SES settings) before going live."
fi
chown -R gm:www-data /srv/gm
chmod 640 /srv/gm/env

cp /srv/gm/repo/server/deploy/gm.service /etc/systemd/system/gm.service
cp /srv/gm/repo/server/deploy/nginx.conf /etc/nginx/sites-available/gm
ln -sf /etc/nginx/sites-available/gm /etc/nginx/sites-enabled/gm
rm -f /etc/nginx/sites-enabled/default

# log files for the cron jobs (deploy/gm.cron, installed by deploy.sh)
for log in gm-backup gm-purge gm-import; do touch /var/log/$log.log && chown gm /var/log/$log.log; done

systemctl daemon-reload
systemctl enable gm
bash /srv/gm/repo/server/deploy/deploy.sh

echo
echo "Done. Next steps (see server/README.md):"
echo "  1. Edit /srv/gm/env, then: sudo systemctl restart gm"
echo "  2. Point the DNS of gmfuneraire.fr to this server, then: sudo certbot --nginx -d gmfuneraire.fr -d www.gmfuneraire.fr"
