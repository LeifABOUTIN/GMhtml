#!/usr/bin/env bash
# Publish the latest version of the branch: sudo bash /srv/gm/repo/server/deploy/deploy.sh
set -euo pipefail

cd /srv/gm/repo
sudo -u gm git pull --ff-only

# static website: everything except the server code and git metadata
rsync -a --delete --exclude server/ --exclude .git/ --exclude '.git*' /srv/gm/repo/ /srv/gm/www/
# browsers keep css/js for 7 days (nginx): give their links a version so a deploy is seen at once
v=$(stat -c %Y /srv/gm/www/css/site.css)
sed -i -E "s#(css/site\.css|script/[a-z]+\.js)(\?v=[0-9]+)?\"#\1?v=$v\"#g" /srv/gm/www/*.html /srv/gm/www/pages/*.html
chown -R gm:www-data /srv/gm/www

sudo -u gm /srv/gm/venv/bin/pip install -q -r server/requirements.txt
cd server
sudo -u gm bash -c 'set -a && . /srv/gm/env && /srv/gm/venv/bin/python manage.py migrate --noinput && /srv/gm/venv/bin/python manage.py collectstatic --noinput -v 0'

# scheduled jobs (backup, purge, Facebook/Instagram import)
cp /srv/gm/repo/server/deploy/gm.cron /etc/cron.d/gm && chmod 644 /etc/cron.d/gm
for log in gm-backup gm-purge gm-import; do touch /var/log/$log.log && chown gm /var/log/$log.log; done

systemctl restart gm
nginx -t && systemctl reload nginx
echo "Deployed $(sudo -u gm git -C /srv/gm/repo rev-parse --short HEAD)"
