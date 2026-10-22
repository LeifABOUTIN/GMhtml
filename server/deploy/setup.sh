#!/usr/bin/env bash
# First-time setup of a fresh Ubuntu 24.04 EC2 instance. Run as root:
#   curl -fsSL https://raw.githubusercontent.com/LeifABOUTIN/GMhtml/memorials/server/deploy/setup.sh | sudo bash
# or, after cloning: sudo bash server/deploy/setup.sh
#
# Optional settings (environment variables):
#   DOMAINS="beta.gmfuneraire.fr"   addresses served (default: gmfuneraire.fr www.gmfuneraire.fr); the first is the main one
#   BETA_PASSWORD=…                 ask for user "beta" + this password on the whole site, and keep it out of search engines
#   CERTBOT_EMAIL=…                 get the HTTPS certificate right away (the DNS must already point to this server)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/LeifABOUTIN/GMhtml.git}"
BRANCH="${BRANCH:-memorials}"
DOMAINS="${DOMAINS:-gmfuneraire.fr www.gmfuneraire.fr}"
MAIN_DOMAIN="${DOMAINS%% *}"

apt-get update
apt-get install -y nginx python3-venv sqlite3 rsync git openssl unzip certbot python3-certbot-nginx
# AWS CLI from the official installer: the snap version refuses users whose home is outside /home (gm's is /srv/gm)
if [ ! -x /usr/local/bin/aws ]; then
	curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip
	unzip -q -o /tmp/awscliv2.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscliv2.zip
fi

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
		-e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=${DOMAINS// /,}|" \
		-e "s|^SITE_URL=.*|SITE_URL=https://$MAIN_DOMAIN|" \
		-e "s|^#DJANGO_DATA_DIR=.*|DJANGO_DATA_DIR=/srv/gm/data|" \
		/srv/gm/env
	echo ">>> Edit /srv/gm/env (Google + SES settings) before going live."
fi
chown -R gm:www-data /srv/gm
chmod 640 /srv/gm/env

cp /srv/gm/repo/server/deploy/gm.service /etc/systemd/system/gm.service
if [ ! -f /etc/nginx/sites-available/gm ]; then  # never overwrite: certbot adds the HTTPS part to this file
	sed "s|^\(\s*server_name\) .*;|\1 $DOMAINS;|" /srv/gm/repo/server/deploy/nginx.conf >/etc/nginx/sites-available/gm
fi
ln -sf /etc/nginx/sites-available/gm /etc/nginx/sites-enabled/gm
rm -f /etc/nginx/sites-enabled/default

if [ -n "${BETA_PASSWORD:-}" ]; then
	printf 'beta:%s\n' "$(openssl passwd -apr1 "$BETA_PASSWORD")" >/etc/nginx/gm-beta.htpasswd
	chown root:www-data /etc/nginx/gm-beta.htpasswd && chmod 640 /etc/nginx/gm-beta.htpasswd
	cat >/etc/nginx/snippets/gm-access.conf <<'NGINX'
auth_basic "Pompes Funebres GM - version beta";
auth_basic_user_file /etc/nginx/gm-beta.htpasswd;
add_header X-Robots-Tag "noindex, nofollow" always;
NGINX
fi

# log files for the cron jobs (deploy/gm.cron, installed by deploy.sh)
for log in gm-backup gm-purge gm-import; do touch /var/log/$log.log && chown gm /var/log/$log.log; done

systemctl daemon-reload
systemctl enable gm
bash /srv/gm/repo/server/deploy/deploy.sh

CERT_ARGS=""
for d in $DOMAINS; do CERT_ARGS="$CERT_ARGS -d $d"; done
if [ -n "${CERTBOT_EMAIL:-}" ]; then
	certbot --nginx --non-interactive --agree-tos --redirect -m "$CERTBOT_EMAIL" $CERT_ARGS
fi

echo
echo "Done. Next steps (see server/README.md):"
echo "  1. Edit /srv/gm/env, then: sudo systemctl restart gm"
[ -n "${CERTBOT_EMAIL:-}" ] || echo "  2. Point the DNS of $DOMAINS to this server, then: sudo certbot --nginx$CERT_ARGS"
