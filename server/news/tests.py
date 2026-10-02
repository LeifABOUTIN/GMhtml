import io
import shutil
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from PIL import Image

from . import social
from .admin import PostAdmin
from .importer import sync_source
from .models import Post

T0 = datetime(2026, 9, 30, 12, 0, tzinfo=dt_timezone.utc)


def jpeg_bytes():
	buf = io.BytesIO()
	Image.new("RGB", (2400, 1800), "green").save(buf, "JPEG")
	return buf.getvalue()


def fake_download(url):
	if "broken" in url:
		raise social.MetaAPIError("404")
	return jpeg_bytes()


def sp(source, ext_id, text, days_ago=0, images=("https://cdn/1.jpg",), video=False):
	return social.SocialPost(source, ext_id, text, T0 - timedelta(days=days_ago), f"https://{source}.com/{ext_id}",
		list(images), video)


class MediaMixin:
	def setUp(self):
		self.media = tempfile.mkdtemp()
		self.override = override_settings(MEDIA_ROOT=self.media)
		self.override.enable()

	def tearDown(self):
		self.override.disable()
		shutil.rmtree(self.media, ignore_errors=True)


class ImporterTests(MediaMixin, TestCase):
	def sync(self, source, posts):
		return sync_source(source, posts, download=fake_download)

	def test_creates_posts_with_local_images(self):
		stats = self.sync("facebook", [sp("facebook", "1", "Fermeture exceptionnelle le 11 novembre. Merci.",
			images=["https://cdn/1.jpg", "https://cdn/broken.jpg"])])
		post = Post.objects.get()
		self.assertEqual(post.display_title, "Fermeture exceptionnelle le 11 novembre")
		self.assertEqual(post.slug, "fermeture-exceptionnelle-le-11-novembre")
		self.assertEqual(post.images.count(), 1)
		self.assertEqual(post.images.get().width, 1600)
		self.assertEqual(stats["créées"], 1)
		self.assertEqual(stats["images en erreur"], 1)

	def test_second_run_updates_without_duplicating(self):
		self.sync("facebook", [sp("facebook", "1", "Ancien texte de la publication")])
		stats = self.sync("facebook", [sp("facebook", "1", "Texte corrigé de la publication")])
		self.assertEqual(Post.objects.get().text, "Texte corrigé de la publication")
		self.assertEqual(Post.objects.get().images.count(), 1)
		self.assertEqual(stats, {"mises à jour": 1})

	def test_locked_post_is_left_alone(self):
		self.sync("facebook", [sp("facebook", "1", "Texte d'origine sur Facebook")])
		Post.objects.update(text="Texte retouché par l'agence", locked=True, is_published=False)
		self.sync("facebook", [sp("facebook", "1", "Texte d'origine sur Facebook")])
		post = Post.objects.get()
		self.assertEqual(post.text, "Texte retouché par l'agence")
		self.assertFalse(post.is_published)

	def test_deleted_on_facebook_is_hidden_but_older_posts_untouched(self):
		self.sync("facebook", [sp("facebook", "new", "Publication récente", 1), sp("facebook", "gone", "Supprimée", 2),
			sp("facebook", "old", "Très ancienne publication", 400)])
		# the API now only returns the last few posts, and "gone" has been deleted
		self.sync("facebook", [sp("facebook", "new", "Publication récente", 1), sp("facebook", "x", "Autre", 3)])
		visible = set(Post.objects.filter(is_published=True).values_list("external_id", flat=True))
		self.assertEqual(visible, {"new", "x", "old"})

	def test_opt_out_tag(self):
		self.sync("facebook", [sp("facebook", "1", "Photo privée de l'équipe #PasDeSite")])
		self.assertFalse(Post.objects.exists())
		self.sync("facebook", [sp("facebook", "2", "Publication normale")])
		self.sync("facebook", [sp("facebook", "2", "Publication normale #pasdesite")])  # tag added afterwards
		self.assertFalse(Post.objects.get().is_published)

	def test_instagram_copy_of_facebook_post_is_skipped(self):
		self.sync("facebook", [sp("facebook", "1", "Notre agence de Soisy sera fermée le 11 novembre. 🌹")])
		stats = self.sync("instagram", [
			sp("instagram", "a", "Notre agence de SOISY sera fermée le 11 novembre ! #toussaint"),
			sp("instagram", "b", "Une publication uniquement sur Instagram, avec un autre texte"),
		])
		self.assertEqual(stats["doublons Facebook ignorés"], 1)
		self.assertEqual(set(Post.objects.values_list("source", "external_id")),
			{("facebook", "1"), ("instagram", "b")})

	def test_admin_edit_locks_imported_post(self):
		self.sync("facebook", [sp("facebook", "1", "Texte importé")])
		post = Post.objects.get()
		post.text = "Corrigé"
		PostAdmin(Post, None).save_model(None, post, SimpleNamespace(changed_data=["text"]), change=True)
		self.assertTrue(Post.objects.get().locked)


@override_settings(META_PAGE_ID="42", META_PAGE_TOKEN="token", META_INSTAGRAM_ID="", ADMIN_EMAILS=["boss@example.com"])
class CommandTests(MediaMixin, TestCase):
	@override_settings(META_PAGE_TOKEN="")
	def test_not_configured_is_a_no_op(self):
		out = StringIO()
		call_command("import_social_posts", stdout=out)
		self.assertIn("non configuré", out.getvalue())

	@mock.patch("news.social.download", side_effect=fake_download)
	@mock.patch("news.social.fetch_instagram")
	@mock.patch("news.social.instagram_account_id", return_value="17841")
	@mock.patch("news.social.fetch_facebook")
	def test_imports_both_networks(self, fetch_fb, ig_id, fetch_ig, _download):
		fetch_fb.return_value = [sp("facebook", "1", "Bonjour depuis Facebook")]
		fetch_ig.return_value = [sp("instagram", "a", "Bonjour depuis Instagram, autre publication")]
		out = StringIO()
		call_command("import_social_posts", stdout=out)
		self.assertEqual(Post.objects.count(), 2)
		fetch_ig.assert_called_once_with("17841", "token", mock.ANY, 50)
		self.assertIn("Facebook : 1 créées", out.getvalue())

	@mock.patch("news.social.fetch_facebook", side_effect=social.MetaAPIError("HTTP 190 Error validating access token"))
	@mock.patch("news.social.instagram_account_id", return_value=None)
	def test_failure_raises_and_emails_admins(self, *_):
		with self.assertRaises(CommandError):
			call_command("import_social_posts", stdout=StringIO())
		self.assertEqual(mail.outbox[0].to, ["boss@example.com"])
		self.assertIn("access token", mail.outbox[0].body)
		self.assertIn("aucun compte Instagram", mail.outbox[0].body)


class ViewTests(TestCase):
	def test_only_published_posts_are_listed(self):
		Post.objects.create(text="Visible ici", published_at=T0)
		hidden = Post.objects.create(text="Cachée", published_at=T0, is_published=False)
		page = self.client.get("/actualites/")
		self.assertContains(page, "Visible ici")
		self.assertNotContains(page, "Cachée")
		self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)

	def test_detail_links_to_original_video(self):
		post = Post.objects.create(source="instagram", external_id="9", text="Hommage en vidéo", published_at=T0,
			permalink="https://instagram.com/p/9", is_video=True)
		self.assertContains(self.client.get(post.get_absolute_url()), "Voir la vidéo sur Instagram")
