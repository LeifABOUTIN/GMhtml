import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

from .qr import qr_png

log = logging.getLogger(__name__)


def send_private_comment(comment):
	"""Email a private message to each family address. Returns True if all were sent."""
	memorial = comment.memorial
	body = render_to_string("emails/private_comment.txt", {
		"comment": comment,
		"memorial": memorial,
		"page_url": settings.SITE_URL + memorial.get_absolute_url(),
	})
	subject = f"Un message de {comment.author_name} en mémoire de {memorial.full_name}"
	reply_to = [comment.author_email] if comment.author_email else None
	attachments = []
	for i, photo in enumerate(comment.photos.all(), start=1):
		with photo.image.open("rb") as f:
			attachments.append((f"photo-{i}.jpg", f.read(), "image/jpeg"))
	ok = True
	# one email per address so family members don't see each other's addresses
	for to in memorial.family_email_list:
		try:
			EmailMessage(subject, body, to=[to], reply_to=reply_to, attachments=attachments).send()
		except Exception:
			log.exception("Private comment %s could not be sent to %s", comment.pk, to)
			ok = False
	return ok


def notify_moderators(comment):
	if not settings.MODERATION_EMAILS:
		return
	body = render_to_string("emails/moderation.txt", {
		"comment": comment,
		"admin_url": settings.SITE_URL + reverse("admin:memorials_comment_change", args=[comment.pk]),
	})
	try:
		EmailMessage(
			f"Message à valider – {comment.memorial.full_name}", body, to=settings.MODERATION_EMAILS
		).send()
	except Exception:
		log.exception("Moderation email for comment %s could not be sent", comment.pk)


def send_qr_to_family(memorial):
	"""Email the page's address and its QR code (PNG) to each family address. Returns (sent, failed)."""
	body = render_to_string("emails/qr_family.txt", {"memorial": memorial, "page_url": memorial.public_url})
	attachment = (f"qr-code-{memorial.slug}.png", qr_png(memorial.public_url), "image/png")
	sent = failed = 0
	# one email per address so family members don't see each other's addresses
	for to in memorial.family_email_list:
		try:
			EmailMessage(f"La page en mémoire de {memorial.full_name}", body, to=[to],
				attachments=[attachment]).send()
			sent += 1
		except Exception:
			log.exception("QR code of memorial %s could not be sent to %s", memorial.pk, to)
			failed += 1
	return sent, failed
