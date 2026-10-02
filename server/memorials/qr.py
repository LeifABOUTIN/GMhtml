"""QR codes as SVG, generated on the server with segno (pure Python, no system dependencies)."""

import io

import segno


def qr_svg(url, standalone=False):
	"""SVG of a QR code pointing to url.

	standalone=False returns an <svg> element to embed in a page (it scales to its CSS size);
	standalone=True returns a complete .svg file to download and send to a printer.
	Error correction "M" survives a creased or slightly smudged card."""
	qr = segno.make(url, error="m", micro=False)
	if standalone:
		buf = io.BytesIO()
		qr.save(buf, kind="svg", scale=10, border=4, dark="#000000", light="#ffffff")
		return buf.getvalue().decode("utf-8")
	return qr.svg_inline(scale=10, border=4, dark="#000000", light="#ffffff", omitsize=True)
