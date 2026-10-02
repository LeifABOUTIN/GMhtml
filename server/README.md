# GM website server – memorial pages ("avis de décès")

The static website (repo root) is served as-is by **nginx**. A small **Django** app adds:

- `/avis-de-deces/` – list + search of published memorial pages, and one page per deceased person
- condolence messages on each page:
  - **public** → hidden until an admin approves it (admins get an email)
  - **private** → never published, emailed to the family addresses set on the page, then deleted after 30 days
- ceremony steps (levée du corps, cérémonie, inhumation…) each with an « Itinéraire » Google Maps link
- up to 3 photos per message (resized, location data removed; photos of private messages are e-mailed to the
  family and never served by the website)
- a QR code for each page, printable as an A4 poster or 8 cards to take away (staff only: `/avis-de-deces/<page>/qr/`)
- `/actualites/` – news page fed every morning with the agency's Facebook and Instagram posts (see "Actualités")
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

Open http://127.0.0.1:8002/ – Django serves the whole site in development.

Run the tests with `.venv\Scripts\python manage.py test memorials`. Emails are printed in the
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

### 5. Actualités: Facebook & Instagram import

The import reads the agency's **own** Page through the Meta Graph API with one Page access token. The Instagram
account must be a professional (business or creator) account **linked to the Facebook Page**
(Facebook Page → Settings → Linked accounts → Instagram).

1. https://developers.facebook.com → *My apps → Create app*, type **Business**, name "GM site". It can stay in
   development mode: it only reads a Page you administer. The person doing this must be admin of the Page.
2. *Tools → Graph API Explorer*: choose the app, *Get User Access Token* with the permissions
   `pages_show_list`, `pages_read_engagement`, `instagram_basic` (add `business_management` if the Page belongs
   to a Business portfolio). Click *Generate*.
3. *Tools → Access Token Debugger*: paste that token, click **Extend Access Token**, copy the long-lived token.
4. Back in the Explorer, with the long-lived token, run `GET me/accounts`. For the GM Page copy its `id` and
   `access_token`: a Page token obtained this way does not expire.
5. In `/srv/gm/env`: `META_PAGE_ID=…`, `META_PAGE_TOKEN=…`, then try it once by hand:
   `cd /srv/gm/repo/server && sudo -u gm bash -c 'set -a && . /srv/gm/env && /srv/gm/venv/bin/python manage.py import_social_posts'`

After that it runs every day at 7:00 (`deploy/gm.cron`, log in `/var/log/gm-import.log`). If the token is ever
revoked (password change, admin removed from the Page…) the admins receive an e-mail; redo steps 2-5.
`META_GRAPH_VERSION` must be a version Meta still supports (they are retired after about two years).

What the import does:
- new posts → created with their photos copied to the site (Meta's image links expire); videos are not copied,
  the post links to them instead;
- posts edited on Facebook/Instagram → updated; deleted there → hidden here;
- a post also published on Instagram with the same text is only taken once (from Facebook);
- add **#pasdesite** to a post to keep it off the website;
- a post you edit, hide or publish in the admin is no longer touched by the import ("ne plus mettre à jour
  automatiquement" is ticked for you). Posts can also be written directly in the admin.

### Updating the site later

Push to the `memorials` branch, then on the server:

```bash
sudo bash /srv/gm/repo/server/deploy/deploy.sh
```

### Day-to-day

- Admin: https://gmfuneraire.fr/admin/ → "Se connecter avec Google".
- *Avis de décès → Ajouter*: name, dates, photo, text, family email(s), tick "publié". Add one line per
  ceremony step in *Étapes de la cérémonie* (the address gives the « Itinéraire » button).
- QR code: column « QR code » in the list, or the « QR code pour la cérémonie » box on the notice →
  *Affiche A4* or *Cartes à emporter*, then « Imprimer » (A4, no margins, 100 %).
- Messages with photos: open the message, delete any unsuitable photo (*Supprimer* box), then publish.
- *Actualités*: imported every morning; hide or edit a post from the admin if needed.
- Old messages are deleted every night: private ones (sent or failed) and refused public ones after 30 days
  (`PRIVATE_COMMENT_RETENTION_DAYS`, `REJECTED_COMMENT_RETENTION_DAYS`).
- *Messages*: filter "En attente de validation", select, action "Publier" or "Refuser".
- Logs: `journalctl -u gm -f` · import: `/var/log/gm-import.log` · Backups: `/srv/gm/data/backups` and the S3 bucket.
- Restore a backup: `gunzip db-DATE.sqlite3.gz && sudo systemctl stop gm && cp db-DATE.sqlite3 /srv/gm/data/db.sqlite3 && sudo systemctl start gm`
