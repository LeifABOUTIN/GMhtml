#!/usr/bin/env bash
# Nightly backup (cron, as user gm): database snapshot + photos, copied to S3.
# Requires BACKUP_BUCKET in /srv/gm/env and an EC2 instance role allowed to write to it.
set -euo pipefail
set -a; . /srv/gm/env; set +a
export PATH="/usr/local/bin:$PATH"  # cron's PATH doesn't include the AWS CLI

STAMP=$(date +%Y-%m-%d)
DIR=/srv/gm/data/backups
cd "$DIR"  # find/aws fail if started from a folder user gm cannot read (e.g. via sudo from /home/ubuntu)
sqlite3 /srv/gm/data/db.sqlite3 ".backup '$DIR/db-$STAMP.sqlite3'"
gzip -f "$DIR/db-$STAMP.sqlite3"
find "$DIR" -name 'db-*.sqlite3.gz' -mtime +14 -delete  # keep two weeks locally

if [ -n "${BACKUP_BUCKET:-}" ]; then
	aws s3 cp "$DIR/db-$STAMP.sqlite3.gz" "s3://$BACKUP_BUCKET/db/" --only-show-errors
	# private message photos are deleted after 30 days: keep them out of the backups too
	aws s3 sync /srv/gm/data/media "s3://$BACKUP_BUCKET/media/" --exclude "messages/prive/*" --only-show-errors
fi
echo "$(date -Is) backup ok"
