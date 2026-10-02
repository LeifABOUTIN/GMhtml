# GM website server – memorial pages ("avis de décès")

The static website (repo root) is served as-is by **nginx**. A small **Django** app adds:

- `/avis-de-deces/` – list + search of published memorial pages, and one page per deceased person
- condolence messages on each page:
  - **public** → hidden until an admin approves it (admins get an email)
  - **private** → never published, emailed to the family addresses set on the page, then deleted after 30 days
- `/admin/` – create / edit / delete memorial pages, approve or reject messages. Sign-in with **Google**,
  restricted to the addresses in `ADMIN_EMAILS`.

Data lives in SQLite (`/srv/gm/data/db.sqlite3`) with photos in `/srv/gm/data/media`, backed up nightly to S3.

```
server/
  gm/            Django project settings & URLs
  memorials/     models, admin, views, emails, templates
  templates/     base layout (same header/footer as the site), emails, admin login
  deploy/        nginx, systemd, setup / deploy / backup scripts
```

## Run it on your computer

```powershell
cd server
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # set DJANGO_DEBUG=1, ADMIN_EMAILS=your Google address
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py runserver 127.0.0.1:8002
```

Open http://127.0.0.1:8002/ – Django serves the whole site in development. Emails are printed in the
terminal instead of being sent while `EMAIL_HOST` is empty.

Google sign-in needs `GOOGLE_CLIENT_ID/SECRET` (step 2 below). Without it, create an emergency admin with
`python manage.py createsuperuser` and use "Connexion de secours" on the login page.

## Going live on EC2

### 1. Launch the server

- EC2 → Launch instance: **Ubuntu 24.04**, `t4g.small` (or `t3.small`), 20 GB disk, region **eu-west-3 (Paris)**.
- Security group: allow **22** (SSH, from your IP only), **80** and **443** (everyone).
- Allocate an **Elastic IP** and associate it with the instance.
- Create an S3 bucket for backups (e.g. `gmfuneraire-backups`, private) and attach an **IAM role** to the
  instance allowing `s3:PutObject` / `s3:ListBucket` on that bucket.

SSH in, then:

```bash
curl -fsSL https://raw.githubusercontent.com/LeifABOUTIN/GMhtml/memorials/server/deploy/setup.sh | sudo bash
```

### 2. Google sign-in

1. https://console.cloud.google.com → create a project "GM site".
2. *APIs & Services → OAuth consent screen*: External, app name "GM – Administration", your email.
3. *Credentials → Create credentials → OAuth client ID → Web application*, authorised redirect URIs:
   - `https://gmfuneraire.fr/accounts/google/login/callback/`
   - `http://127.0.0.1:8002/accounts/google/login/callback/` (for local testing)
4. Put the client ID and secret in `/srv/gm/env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`), and the admins'
   Google addresses in `ADMIN_EMAILS`.

### 3. Email with Amazon SES

1. SES console (eu-west-3) → *Identities → Create identity → Domain* `gmfuneraire.fr`, add the DKIM DNS
   records it gives you.
2. *Account dashboard → Request production access* (otherwise SES only sends to verified addresses).
3. *SMTP settings → Create SMTP credentials*, then in `/srv/gm/env`:
   `EMAIL_HOST=email-smtp.eu-west-3.amazonaws.com`, `EMAIL_HOST_USER=…`, `EMAIL_HOST_PASSWORD=…`

Then `sudo systemctl restart gm`.

### 4. Switch the domain from S3 to the server

1. Point the DNS **A** records of `gmfuneraire.fr` and `www.gmfuneraire.fr` to the Elastic IP
   (if the domain is in Route 53, edit the records that currently point to S3/CloudFront).
2. Once the DNS answers with the new IP: `sudo certbot --nginx -d gmfuneraire.fr -d www.gmfuneraire.fr`
   (free HTTPS certificate, renewed automatically).
3. Keep the S3 bucket for a few days as a fallback, then disable it.

### Updating the site later

Push to the `memorials` branch, then on the server:

```bash
sudo bash /srv/gm/repo/server/deploy/deploy.sh
```

### Day-to-day

- Admin: https://gmfuneraire.fr/admin/ → "Se connecter avec Google".
- *Avis de décès → Ajouter*: name, dates, photo, text, ceremony, family email(s), tick "publié".
- *Messages*: filter "En attente de validation", select, action "Publier" or "Refuser".
- Logs: `journalctl -u gm -f` · Backups: `/srv/gm/data/backups` and the S3 bucket.
- Restore a backup: `gunzip db-DATE.sqlite3.gz && sudo systemctl stop gm && cp db-DATE.sqlite3 /srv/gm/data/db.sqlite3 && sudo systemctl start gm`
