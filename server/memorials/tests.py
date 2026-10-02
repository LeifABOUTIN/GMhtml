import io
import os
import shutil
import tempfile
from datetime import date, timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .adapters import AdminOnlySocialAccountAdapter
from PIL import Image

from .models import CeremonyStep, Comment, CommentPhoto, Memorial


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


def jpeg_upload(name="souvenir.jpg", size=(3000, 2000)):
	buf = io.BytesIO()
	Image.new("RGB", size, "blue").save(buf, "JPEG")
	return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(MODERATION_EMAILS=["admin@example.com"])
class CommentPhotoTests(TestCase):
	def setUp(self):
		cache.clear()
		self.media = tempfile.mkdtemp()
		self.override = override_settings(MEDIA_ROOT=self.media)
		self.override.enable()
		self.m = make_memorial()

	def tearDown(self):
		self.override.disable()
		shutil.rmtree(self.media, ignore_errors=True)

	def post(self, photos, **data):
		return self.client.post(self.m.get_absolute_url(), {
			"author_name": "Ami", "relationship": "voisin", "message": "Pensées", "visibility": "public",
			"photos": photos, **data})

	def test_public_photos_are_resized_and_shown_after_approval(self):
		self.post([jpeg_upload(), jpeg_upload("b.png")])
		c = Comment.objects.get()
		self.assertEqual(c.relationship, "voisin")
		photos = list(c.photos.all())
		self.assertEqual(len(photos), 2)
		self.assertTrue(photos[0].image.name.startswith("messages/public/"))
		self.assertEqual(max(photos[0].width, photos[0].height), 1600)
		self.assertIn("Photos jointes : 2", mail.outbox[0].body)
		self.assertNotContains(self.client.get(self.m.get_absolute_url()), photos[0].image.url)
		c.status = Comment.Status.APPROVED
		c.save()
		page = self.client.get(self.m.get_absolute_url())
		self.assertContains(page, photos[0].image.url)
		self.assertContains(page, "(voisin)")

	def test_too_many_photos(self):
		r = self.post([jpeg_upload() for _ in range(4)])
		self.assertFalse(Comment.objects.exists())
		self.assertContains(r, "3 photos maximum")

	def test_not_an_image(self):
		r = self.post([SimpleUploadedFile("virus.jpg", b"MZ\x90 not a picture", content_type="image/jpeg")])
		self.assertFalse(Comment.objects.exists())
		self.assertContains(r, "pas une photo lisible")

	def test_private_photos_are_emailed_and_stored_apart(self):
		self.post([jpeg_upload()], visibility="private")
		photo = CommentPhoto.objects.get()
		self.assertTrue(photo.image.name.startswith("messages/prive/"))
		self.assertEqual([a[0] for a in mail.outbox[0].attachments], ["photo-1.jpg"])
		self.assertEqual(mail.outbox[0].attachments[0][2], "image/jpeg")

	def test_purge_deletes_photo_files(self):
		self.post([jpeg_upload()], visibility="private")
		path = CommentPhoto.objects.get().image.path
		self.assertTrue(os.path.exists(path))
		Comment.objects.update(created_at=timezone.now() - timedelta(days=31))
		call_command("purge_private_comments", stdout=StringIO())
		self.assertFalse(CommentPhoto.objects.exists())
		self.assertFalse(os.path.exists(path))


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
