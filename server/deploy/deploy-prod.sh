#!/usr/bin/env bash
# Publish the public site (www.gmfuneraire.fr) from the `redesign` branch:
#   sudo bash /srv/gm/repo/server/deploy/deploy-prod.sh
# Separate from deploy.sh, which publishes the beta from `memorials`. Run this one for changes to the
# public pages; the contact endpoint itself is Django, so it follows deploy.sh.
set -euo pipefail

BRANCH="${BRANCH:-redesign}"
cd /srv/gm/repo
sudo -u gm git fetch -q origin "$BRANCH"
commit=$(sudo -u gm git rev-parse --short FETCH_HEAD)

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
sudo -u gm git archive FETCH_HEAD | tar -x -C "$tmp"
rm -rf "$tmp/server"
mkdir -p /srv/gm/www-prod /var/www/certbot
rsync -a --delete --exclude '.git*' "$tmp"/ /srv/gm/www-prod/
# browsers keep css/js for 7 days (nginx): give their links a version so a deploy is seen at once
v=$(stat -c %Y /srv/gm/www-prod/css/site.css /srv/gm/www-prod/script/*.js | sort -n | tail -1)
sed -i -E "s#(css/site\.css|script/[a-z]+\.js)(\?v=[0-9]+)?\"#\1?v=$v\"#g" /srv/gm/www-prod/*.html /srv/gm/www-prod/pages/*.html
chown -R gm:www-data /srv/gm/www-prod

cp /srv/gm/repo/server/deploy/nginx-prod.conf /etc/nginx/sites-available/gm-prod
ln -sf /etc/nginx/sites-available/gm-prod /etc/nginx/sites-enabled/gm-prod
nginx -t && systemctl reload nginx
echo "Public site deployed: $commit"
