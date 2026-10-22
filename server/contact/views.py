"""Endpoint used by script/form.js on pages/contact.html (replaces the former AWS Lambda)."""

import json
import logging
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ContactRequest

log = logging.getLogger(__name__)

RATE_LIMIT = 5  # requests per visitor…
RATE_WINDOW = 10 * 60  # …per 10 minutes
PHONE = re.compile(r"^\+?[0-9 .()-]{6,25}$")


@csrf_exempt  # the static contact page has no CSRF token; the endpoint only stores a request
@require_POST
def submit(request):
	try:
		data = json.loads(request.body or b"{}")
	except ValueError:
		return JsonResponse({"error": "invalid"}, status=400)
	if not isinstance(data, dict):
		return JsonResponse({"error": "invalid"}, status=400)
	if data.get("website"):  # honeypot field: pretend it worked
		return JsonResponse({"ok": True})

	name = str(data.get("name", "")).strip()[:150]
	message = str(data.get("message") or "").strip()[:5000]
	contact = str(data.get("contact", "")).strip()[:254]
	reason = data.get("reason") if data.get("reason") in ContactRequest.Reason.values else ContactRequest.Reason.INFO
	email = phone = ""
	if "@" in contact:
		try:
			validate_email(contact)
			email = contact
		except ValidationError:
			pass
	elif PHONE.match(contact):
		phone = contact
	if not name or not (email or phone):
		return JsonResponse({"error": "missing"}, status=400)

	if _rate_limited(request):
		return JsonResponse({"error": "rate"}, status=429)

	req = ContactRequest.objects.create(reason=reason, name=name, email=email, phone=phone, message=message)
	_notify_staff(req)
	return JsonResponse({"ok": True})


def _notify_staff(req):
	"""Same e-mail as the old Lambda sent; the request is already saved if this fails."""
	if not settings.MODERATION_EMAILS:
		return
	body = render_to_string("emails/contact_request.txt", {
		"req": req,
		"admin_url": settings.SITE_URL + reverse("admin:contact_contactrequest_change", args=[req.pk]),
	})
	try:
		EmailMessage(f"Nouvelle demande de contact ({req.get_reason_display()}) – {req.name}", body,
			to=settings.MODERATION_EMAILS, reply_to=[req.email] if req.email else None).send()
	except Exception:
		log.exception("Notification for contact request %s could not be sent", req.pk)


def _rate_limited(request):
	ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")
	key = f"contact-rate:{ip}"
	now = time.time()
	count, window_end = cache.get(key) or (0, 0)
	if now >= window_end:
		count, window_end = 0, now + RATE_WINDOW
	if count >= RATE_LIMIT:
		return True
	cache.set(key, (count + 1, window_end), max(1, int(window_end - now)))
	return False
