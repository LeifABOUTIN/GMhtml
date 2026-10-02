import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

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
	ok = True
	# one email per address so family members don't see each other's addresses
	for to in memorial.family_email_list:
		try:
			EmailMessage(subject, body, to=[to], reply_to=reply_to).send()
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
