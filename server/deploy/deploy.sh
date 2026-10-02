#!/usr/bin/env bash
# Publish the latest version of the branch: sudo bash /srv/gm/repo/server/deploy/deploy.sh
set -euo pipefail

cd /srv/gm/repo
sudo -u gm git pull --ff-only

# static website: everything except the server code and git metadata
rsync -a --delete --exclude server/ --exclude .git/ --exclude '.git*' /srv/gm/repo/ /srv/gm/www/
chown -R gm:www-data /srv/gm/www

sudo -u gm /srv/gm/venv/bin/pip install -q -r server/requirements.txt
cd server
sudo -u gm bash -c 'set -a && . /srv/gm/env && /srv/gm/venv/bin/python manage.py migrate --noinput && /srv/gm/venv/bin/python manage.py collectstatic --noinput -v 0'

systemctl restart gm
nginx -t && systemctl reload nginx
echo "Deployed $(sudo -u gm git -C /srv/gm/repo rev-parse --short HEAD)"
