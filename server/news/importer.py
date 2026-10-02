"""Turn SocialPosts from social.py into Post rows: create, update, hide. Run daily by import_social_posts."""

import logging
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from gm.images import InvalidImage, normalise_photo

from . import social
from .models import Post, PostImage

log = logging.getLogger(__name__)
DUPLICATE_WINDOW = timedelta(days=3)


def _opted_out(text):
	tag = settings.SOCIAL_OPT_OUT_TAG.lower()
	return bool(tag) and tag in text.lower()


def _is_copy_of_facebook_post(sp):
	"""The agency often posts the same thing on Facebook and Instagram: keep only the Facebook one."""
	key = social.comparable_text(sp.text)
	if len(key) < 20:  # too short to be sure ("🌹", "Merci !")
		return False
	candidates = Post.objects.filter(source=Post.Source.FACEBOOK,
		published_at__range=(sp.published_at - DUPLICATE_WINDOW, sp.published_at + DUPLICATE_WINDOW))
	return any(social.comparable_text(p.text) == key for p in candidates)


def _add_images(post, urls, stats, download):
	for i, url in enumerate(urls):
		try:
			jpeg, _, _ = normalise_photo(download(url))
		except (social.MetaAPIError, InvalidImage) as e:
			log.warning("Image %s of %s skipped: %s", i, post, e)
			stats["images en erreur"] += 1
			continue
		PostImage.objects.create(post=post, image=ContentFile(jpeg, name=f"{post.slug}-{i + 1}.jpg"), order=i)
		stats["images"] += 1


def sync_source(source, posts, download=None):
	"""posts: the latest SocialPosts of one network, newest first. Returns a Counter of what happened."""
	download = download or social.download  # looked up now, so tests can patch it
	stats = Counter()
	seen = set()
	for sp in posts:
		seen.add(sp.external_id)
		hidden = _opted_out(sp.text)
		post = Post.objects.filter(source=source, external_id=sp.external_id).first()

		if post is None:
			if hidden:
				stats["ignorées (" + settings.SOCIAL_OPT_OUT_TAG + ")"] += 1
				continue
			if source == Post.Source.INSTAGRAM and _is_copy_of_facebook_post(sp):
				stats["doublons Facebook ignorés"] += 1
				continue
			with transaction.atomic():
				post = Post.objects.create(source=source, external_id=sp.external_id, text=sp.text,
					published_at=sp.published_at, permalink=sp.permalink, is_video=sp.is_video)
			_add_images(post, sp.image_urls, stats, download)
			stats["créées"] += 1
			continue

		if post.locked:
			continue  # edited by the agency: leave it alone
		changed = False
		for attr, value in (("text", sp.text), ("permalink", sp.permalink), ("is_video", sp.is_video),
				("is_published", not hidden)):
			if getattr(post, attr) != value:
				setattr(post, attr, value)
				changed = True
		if changed:
			post.save()
			stats["mises à jour"] += 1
		if sp.image_urls and not post.images.exists():
			_add_images(post, sp.image_urls, stats, download)  # images failed to download last time

	# Deleted on the network → hidden here. Only within the period the API just returned,
	# so older posts (beyond the last 50) are never touched.
	if posts:
		oldest = min(sp.published_at for sp in posts)
		gone = (Post.objects.filter(source=source, locked=False, is_published=True, published_at__gte=oldest)
			.exclude(external_id__in=seen))
		stats["masquées (supprimées sur " + source + ")"] += gone.update(is_published=False)
	return +stats  # drop zero counts
