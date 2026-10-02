from datetime import date, timedelta
from io import StringIO
from types import SimpleNamespace

from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from .adapters import AdminOnlySocialAccountAdapter
from .models import Comment, Memorial


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
