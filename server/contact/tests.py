import json
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import ContactRequest

URL = "/contact/envoyer/"


@override_settings(MODERATION_EMAILS=["agence@example.com"], SITE_URL="https://beta.gmfuneraire.fr")
class ContactFormTests(TestCase):
	def setUp(self):
		cache.clear()

	def post(self, **data):
		body = {"reason": "devis", "name": "Jean Dupont", "message": "Bonjour", "contact": "jean@example.com", **data}
		return self.client.post(URL, json.dumps(body), content_type="application/json")

	def test_request_is_saved_and_agency_notified(self):
		r = self.post()
		self.assertEqual(r.status_code, 200)
		req = ContactRequest.objects.get()
		self.assertEqual((req.reason, req.name, req.email, req.status), ("devis", "Jean Dupont", "jean@example.com", "new"))
		self.assertEqual(mail.outbox[0].to, ["agence@example.com"])
		self.assertEqual(mail.outbox[0].reply_to, ["jean@example.com"])
		self.assertIn(f"/admin/contact/contactrequest/{req.pk}/change/", mail.outbox[0].body)

	def test_phone_contact(self):
		self.post(contact="06 12 34 56 78", reason="infos", message=None)
		req = ContactRequest.objects.get()
		self.assertEqual((req.phone, req.email, req.reason, req.message), ("06 12 34 56 78", "", "infos", ""))

	def test_saved_even_if_email_fails(self):
		with self.settings(EMAIL_BACKEND="nonexistent.Backend"):
			self.assertEqual(self.post().status_code, 200)
		self.assertTrue(ContactRequest.objects.exists())

	def test_invalid_requests(self):
		self.assertEqual(self.post(name="").status_code, 400)
		self.assertEqual(self.post(contact="not an address").status_code, 400)
		self.assertEqual(self.client.post(URL, "{broken", content_type="application/json").status_code, 400)
		self.assertEqual(self.client.get(URL).status_code, 405)
		self.assertFalse(ContactRequest.objects.exists())

	def test_honeypot_and_rate_limit(self):
		self.post(website="http://spam")
		self.assertFalse(ContactRequest.objects.exists())
		codes = [self.post().status_code for _ in range(7)]
		self.assertEqual(codes.count(200), 5)
		self.assertEqual(codes[-1], 429)

	def test_purge_after_retention(self):
		old = ContactRequest.objects.create(reason="infos", name="Ancien", phone="0102030405")
		ContactRequest.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=3 * 365 + 1))
		ContactRequest.objects.create(reason="infos", name="Récent", phone="0102030405")
		call_command("purge_contact_requests", stdout=StringIO())
		self.assertEqual(list(ContactRequest.objects.values_list("name", flat=True)), ["Récent"])


class AdminTodoTests(TestCase):
	def test_admin_home_shows_new_requests(self):
		ContactRequest.objects.create(reason="devis", name="A", phone="0102030405")
		admin = get_user_model().objects.create_superuser("boss", "boss@example.com", "x" * 12)
		self.client.force_login(admin)
		page = self.client.get("/admin/")
		self.assertContains(page, "À traiter")
		self.assertContains(page, "nouvelle(s) demande(s) de contact")
		self.assertContains(page, "?status__exact=new")
