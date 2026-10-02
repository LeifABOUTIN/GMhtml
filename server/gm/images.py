"""Shared image handling: every uploaded or imported photo goes through normalise_photo()."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600  # px – plenty for a screen, keeps files around 200-400 KB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "MPO"}  # MPO = some phone JPEGs


class InvalidImage(ValueError):
	pass


def normalise_photo(data):
	"""bytes in → (jpeg bytes, width, height) out.

	Rotates according to the camera orientation, shrinks to MAX_SIDE, and re-encodes as JPEG
	*without* the EXIF block, which on phone photos contains the GPS position of the picture."""
	try:
		with Image.open(io.BytesIO(data)) as probe:
			fmt = probe.format
			probe.verify()  # detects truncated / fake files
		if fmt not in ALLOWED_FORMATS:
			raise InvalidImage(f"format {fmt} non accepté")
		img = Image.open(io.BytesIO(data))
		img.seek(0)  # first frame of a GIF
		img = ImageOps.exif_transpose(img)
	except (UnidentifiedImageError, OSError, SyntaxError) as e:
		raise InvalidImage("fichier image illisible") from e
	if img.mode in ("RGBA", "LA", "P"):
		img = img.convert("RGBA")
		background = Image.new("RGB", img.size, "white")
		background.paste(img, mask=img.getchannel("A"))
		img = background
	else:
		img = img.convert("RGB")
	img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
	out = io.BytesIO()
	img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
	return out.getvalue(), img.width, img.height
