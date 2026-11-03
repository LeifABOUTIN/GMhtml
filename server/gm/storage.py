from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class HashedStaticStorage(ManifestStaticFilesStorage):
	"""File names with a content hash; falls back to the plain name when collectstatic hasn't run (tests, dev)."""

	manifest_strict = False
