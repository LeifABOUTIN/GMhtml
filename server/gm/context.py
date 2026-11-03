"""Template context shared by every page."""

from django.conf import settings


def asset_version(request):
	"""Changes whenever css/site.css changes: added to its URL so browsers don't keep an old copy (cached 7 days)."""
	try:
		return {"asset_version": int((settings.SITE_DIR / "css" / "site.css").stat().st_mtime)}
	except OSError:
		return {"asset_version": 0}
