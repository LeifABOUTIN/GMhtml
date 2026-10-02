from datetime import date, timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .adapters import AdminOnlySocialAccountAdapter
from .models import CeremonyStep, Comment, Memorial


def make_memorial(**kw):
	defaults = dict(first_name="Jeanne", last_name="Exemple", death_date=date(2026, 9, 28),
		announcement="Avis", family_emails="a@example.com, b@example.com", is_published=True)
	return Memorial.objects.create(**{**defaults, **kw})


@override_settings(MODERATION_EMAILS=["admin@example.com"])
class CommentFlowTests(TestCase):
	def setUp(self):
		cache.clear()
		self.m = make_memorial()

	def post(self, **data):
		return self.client.post(self.m.get_absolute_url(), {"author_name": "Ami", "message": "Pensées", **data})

	def test_slug_is_generated_and_unique(self):
		other = make_memorial()
		self.assertEqual(self.m.slug, "jeanne-exemple-2026")
		self.assertEqual(other.slug, "jeanne-exemple-2026-2")

	def test_unpublished_page_is_hidden(self):
		hidden = make_memorial(first_name="Caché", is_published=False)
		self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)
		self.assertNotContains(self.client.get("/avis-de-deces/"), "Caché")

	def test_public_comment_waits_for_approval(self):
		self.post(visibility="public")
		c = Comment.objects.get()
		self.assertEqual(c.status, Comment.Status.PENDING)
		self.assertNotContains(self.client.get(self.m.get_absolute_url()), "Pensées")
		self.assertEqual([e.to for e in mail.outbox], [["admin@example.com"]])
		c.status = Comment.Status.APPROVED
		c.save()
		self.assertContains(self.client.get(self.m.get_absolute_url()), "Pensées")

	def test_private_comment_is_emailed_to_each_family_member(self):
		self.post(visibility="private", author_email="ami@example.com")
		c = Comment.objects.get()
		self.assertEqual(c.status, Comment.Status.SENT)
		self.assertEqual(sorted(e.to[0] for e in mail.outbox), ["a@example.com", "b@example.com"])
		self.assertEqual(mail.outbox[0].reply_to, ["ami@example.com"])
		self.assertIn("Pensées", mail.outbox[0].body)
		self.assertNotContains(self.client.get(self.m.get_absolute_url()), "Pensées")

	def test_private_not_offered_without_family_email(self):
		m = make_memorial(first_name="Pierre", family_emails="")
		self.client.post(m.get_absolute_url(), {"author_name": "A", "message": "x", "visibility": "private"})
		self.assertFalse(Comment.objects.exists())

	def test_honeypot_is_ignored(self):
		self.post(visibility="public", website="http://spam")
		self.assertFalse(Comment.objects.exists())

	def test_rate_limit(self):
		for _ in range(7):
			self.post(visibility="public")
		self.assertEqual(Comment.objects.count(), 5)

	def test_closed_comments(self):
		self.m.comments_open = False
		self.m.save()
		self.post(visibility="public")
		self.assertFalse(Comment.objects.exists())

	def test_purge_old_private_messages(self):
		old = Comment.objects.create(memorial=self.m, author_name="A", message="x", visibility="private",
			status=Comment.Status.SENT)
		Comment.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=31))
		Comment.objects.create(memorial=self.m, author_name="B", message="y", visibility="private",
			status=Comment.Status.SENT)
		call_command("purge_private_comments", stdout=StringIO())
		self.assertEqual(list(Comment.objects.values_list("author_name", flat=True)), ["B"])

	def test_rate_limit_window_does_not_slide(self):
		# 5 messages, then one more every 3 minutes: blocked until 10 minutes after the FIRST message
		with mock.patch("memorials.views.time.time") as now:
			now.return_value = 1_000_000
			for _ in range(5):
				self.post(visibility="public")
			for minutes in (3, 6, 9):
				now.return_value = 1_000_000 + minutes * 60
				self.post(visibility="public")
			self.assertEqual(Comment.objects.count(), 5)
			now.return_value = 1_000_000 + 10 * 60 + 1
			self.post(visibility="public")
		self.assertEqual(Comment.objects.count(), 6)

	def test_purge_failed_private_and_rejected_messages(self):
		def comment(name, visibility, status, days):
			c = Comment.objects.create(memorial=self.m, author_name=name, message="x", visibility=visibility,
				status=status)
			Comment.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=days))

		comment("old-failed", "private", Comment.Status.FAILED, 31)
		comment("new-failed", "private", Comment.Status.FAILED, 2)
		comment("old-rejected", "public", Comment.Status.REJECTED, 31)
		comment("new-rejected", "public", Comment.Status.REJECTED, 2)
		comment("old-pending", "public", Comment.Status.PENDING, 90)
		comment("old-approved", "public", Comment.Status.APPROVED, 90)
		call_command("purge_private_comments", stdout=StringIO())
		self.assertEqual(sorted(Comment.objects.values_list("author_name", flat=True)),
			["new-failed", "new-rejected", "old-approved", "old-pending"])


class CeremonyStepTests(TestCase):
	def test_steps_are_shown_with_maps_link(self):
		m = make_memorial()
		CeremonyStep.objects.create(memorial=m, order=1, title="Cérémonie religieuse", place="Église Saint-Germain",
			address="1 place de l'Église, 95230 Soisy-sous-Montmorency")
		CeremonyStep.objects.create(memorial=m, order=2, title="Inhumation", details="dans l’intimité familiale")
		html = self.client.get(m.get_absolute_url()).content.decode()
		self.assertIn("Cérémonie religieuse", html)
		self.assertIn("https://www.google.com/maps/search/?api=1&amp;query=%C3%89glise+Saint-Germain", html)
		self.assertEqual(html.count("Itinéraire"), 1)  # no address → no directions button
		self.assertLess(html.index("Cérémonie religieuse"), html.index("Inhumation"))


@override_settings(SITE_URL="https://gmfuneraire.fr")
class QRCodeTests(TestCase):
	def setUp(self):
		self.m = make_memorial(is_published=False)  # the agency prints before publishing
		self.staff = get_user_model().objects.create_user("agent", "agent@example.com", "x" * 12, is_staff=True)

	def test_requires_staff(self):
		for name in ("memorials:qr", "memorials:qr_download"):
			r = self.client.get(reverse(name, args=[self.m.slug]))
			self.assertEqual(r.status_code, 302)
			self.assertIn("/admin/login/", r["Location"])

	def test_poster_and_cards(self):
		self.client.force_login(self.staff)
		url = reverse("memorials:qr", args=[self.m.slug])
		poster = self.client.get(url)
		self.assertContains(poster, "<svg")
		self.assertContains(poster, "gmfuneraire.fr/avis-de-deces/jeanne-exemple-2026/")
		self.assertContains(poster, "pas encore publié")
		cards = self.client.get(url + "?format=cartes").content.decode()
		self.assertEqual(cards.count('class="card"'), 8)

	def test_download_svg(self):
		self.client.force_login(self.staff)
		r = self.client.get(reverse("memorials:qr_download", args=[self.m.slug]))
		self.assertEqual(r["Content-Type"], "image/svg+xml")
		self.assertIn('filename="qr-jeanne-exemple-2026.svg"', r["Content-Disposition"])
		self.assertIn(b"<svg", r.content)


@override_settings(ADMIN_EMAILS=["boss@example.com"])
class GoogleAllowListTests(TestCase):
	def sociallogin(self, email, verified=True):
		user = get_user_model()(email=email)
		account = SimpleNamespace(extra_data={"email": email, "email_verified": verified})
		return SimpleNamespace(user=user, account=account, is_existing=False)

	def request(self):
		r = RequestFactory().get("/accounts/google/login/callback/")
		r.session = self.client.session
		r._messages = FallbackStorage(r)
		return r

	def test_allowed_address_becomes_admin(self):
		sl = self.sociallogin("Boss@Example.com")
		adapter = AdminOnlySocialAccountAdapter()
		adapter.pre_social_login(self.request(), sl)
		self.assertTrue(sl.user.is_staff and sl.user.is_superuser)
		self.assertTrue(adapter.is_open_for_signup(self.request(), sl))

	def test_other_address_is_refused(self):
		with self.assertRaises(ImmediateHttpResponse):
			AdminOnlySocialAccountAdapter().pre_social_login(self.request(), self.sociallogin("someone@gmail.com"))

	def test_unverified_email_is_refused(self):
		with self.assertRaises(ImmediateHttpResponse):
			AdminOnlySocialAccountAdapter().pre_social_login(
				self.request(), self.sociallogin("boss@example.com", verified=False))
