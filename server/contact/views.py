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
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ContactRequest

log = logging.getLogger(__name__)

RATE_LIMIT = 5  # requests per visitor…
RATE_WINDOW = 10 * 60  # …per 10 minutes
# a full French number, or an international one; same rule as script/form.js and script/devis.js
PHONE = re.compile(r"^(0[1-9]\d{8}|(\+|00)330?\d{9}|(\+|00)(?!33)\d{8,15})$")


def _is_phone(value):
	return bool(PHONE.match(re.sub(r"[ .()-]", "", value)))


@csrf_exempt  # the static contact page has no CSRF token; the endpoint only e-mails a request
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
	elif _is_phone(contact):
		phone = contact
	if not name or not (email or phone):
		return JsonResponse({"error": "missing"}, status=400)

	if _rate_limited(request):
		return JsonResponse({"error": "rate"}, status=429)

	# requests are only e-mailed now, no longer stored or shown in the admin
	# req = ContactRequest.objects.create(reason=reason, name=name, email=email, phone=phone, message=message)
	req = ContactRequest(reason=reason, name=name, email=email, phone=phone, message=message)
	if not _notify_staff(req):
		return JsonResponse({"error": "mail"}, status=502)  # the page shows its error, the visitor can call instead
	return JsonResponse({"ok": True})


def _notify_staff(req):
	"""Same e-mail as the old Lambda sent. Returns False if it could not be sent (the request is not stored)."""
	if not settings.MODERATION_EMAILS:
		log.error("No MODERATION_EMAILS/ADMIN_EMAILS: contact request from %s not sent", req.name)
		return False
	body = render_to_string("emails/contact_request.txt", {"req": req})
	try:
		EmailMessage(f"Nouvelle demande de contact ({req.get_reason_display()}) – {req.name}", body,
			to=settings.MODERATION_EMAILS, reply_to=[req.email] if req.email else None).send()
	except Exception:
		log.exception("Contact request from %s could not be sent", req.name)
		return False
	return True


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


# --- quote forms: pages/devis-obseques.html and pages/devis-marbrerie.html (e-mailed only) ---

AGENCIES = {"soisy": "Soisy-sous-Montmorency", "saint-leu": "Saint-Leu-la-Forêt", "indifferent": "Peu importe"}
CALLBACK = {"vite": "Dès que possible", "matin": "Le matin", "apres-midi": "L’après-midi", "soir": "En fin de journée"}

# for each form: (field, label, choices, required); choices=None is free text, a set of choices in a list is multiple
QUOTES = {
	"obseques": ("Demande de devis obsèques", [
		("situation", "Situation", {"deces": "Un décès est survenu", "fin-de-vie": "Un proche en fin de vie",
			"prevoyance": "Prévoir mes propres obsèques"}, True),
		("type", "Type d’obsèques", {"inhumation": "Inhumation", "cremation": "Crémation",
			"ne-sait-pas": "Je ne sais pas encore"}, True),
		("ceremonie", "Cérémonie", {"religieuse": "Religieuse", "civile": "Civile", "aucune": "Pas de cérémonie",
			"ne-sait-pas": "Je ne sais pas encore"}, False),
		("extras", "Prestations souhaitées", [{"soins": "Soins de conservation", "fleurs": "Fleurs",
			"avis": "Avis de décès en ligne", "monument": "Monument / marbrerie",
			"demarches": "Aide aux démarches administratives"}], False),
	]),
	"marbrerie": ("Demande de devis marbrerie", [
		("besoin", "Besoin", {"creation": "Nouveau monument", "renovation": "Rénovation d’un monument",
			"gravure": "Gravure / inscription", "entretien": "Entretien / fleurissement"}, True),
		("ville", "Cimetière (ville)", None, True),
	]),
}


@csrf_exempt  # static page, like the contact form
@require_POST
def quote(request):
	try:
		data = json.loads(request.body or b"{}")
	except ValueError:
		return JsonResponse({"error": "invalid"}, status=400)
	if not isinstance(data, dict) or data.get("kind") not in QUOTES:
		return JsonResponse({"error": "invalid"}, status=400)
	if data.get("website"):  # honeypot
		return JsonResponse({"ok": True})

	title, fields = QUOTES[data["kind"]]
	answers = []
	for field, label, choices, required in fields:
		value = data.get(field)
		if choices is None:
			value = str(value or "").strip()[:120]
		elif isinstance(choices, list):
			value = ", ".join(choices[0][v] for v in value if v in choices[0]) if isinstance(value, list) else ""
		else:
			value = choices.get(value, "")
		if required and not value:
			return JsonResponse({"error": "missing", "field": field}, status=400)
		answers.append((label, value or "–"))

	name = str(data.get("name", "")).strip()[:150]
	email, phone = _split_contact(str(data.get("contact", "")).strip()[:254])
	if not name or not (email or phone):
		return JsonResponse({"error": "missing"}, status=400)
	if _rate_limited(request):
		return JsonResponse({"error": "rate"}, status=429)

	body = render_to_string("emails/quote_request.txt", {
		"title": title, "answers": answers, "name": name, "email": email, "phone": phone,
		"agency": AGENCIES.get(data.get("agency"), "Peu importe"),
		"callback": CALLBACK.get(data.get("callback"), "Dès que possible"),
		"message": str(data.get("message") or "").strip()[:2000],
	})
	try:
		EmailMessage(f"{title} – {name}", body, to=settings.MODERATION_EMAILS,
			reply_to=[email] if email else None).send()
	except Exception:
		log.exception("Quote request from %s could not be sent", name)
		return JsonResponse({"error": "mail"}, status=502)
	return JsonResponse({"ok": True})


def _split_contact(contact):
	"""(email, phone) from the single contact field; both empty if it is neither."""
	if "@" in contact:
		try:
			validate_email(contact)
			return contact, ""
		except ValidationError:
			return "", ""
	return ("", contact) if _is_phone(contact) else ("", "")
