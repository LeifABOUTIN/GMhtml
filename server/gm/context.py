"""Template context shared by every page."""

from django.conf import settings


def asset_version(request):
	"""Changes whenever the css or a script changes: added to their URLs so browsers don't keep an old copy
	(nginx lets them cache those files 7 days). Same value as deploy.sh stamps into the static pages."""
	files = [settings.SITE_DIR / "css" / "site.css", *(settings.SITE_DIR / "script").glob("*.js")]
	return {"asset_version": max((int(f.stat().st_mtime) for f in files if f.exists()), default=0)}
