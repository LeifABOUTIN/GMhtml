"""Read the agency's own posts from the Meta Graph API (Facebook Page + linked Instagram account).

Plain Python (no Django) so it can be tested on its own. One Page access token is enough for both:
the Instagram professional account just has to be linked to the Facebook Page.
Every post comes back as a SocialPost; images are only URLs here (Meta's links expire after a while,
so the importer downloads them straight away)."""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GRAPH = "https://graph.facebook.com"
TIMEOUT = 20
MAX_IMAGES = 10


class MetaAPIError(Exception):
	pass


@dataclass
class SocialPost:
	source: str  # "facebook" | "instagram"
	external_id: str
	text: str
	published_at: datetime
	permalink: str
	image_urls: list = field(default_factory=list)
	is_video: bool = False


def _get(url, params):
	try:
		with urlopen(Request(url + "?" + urlencode(params), headers={"User-Agent": "gmfuneraire-site"}),
				timeout=TIMEOUT) as r:
			return json.load(r)
	except HTTPError as e:
		try:
			detail = json.load(e).get("error", {}).get("message", "")
		except Exception:
			detail = ""
		raise MetaAPIError(f"HTTP {e.code} {detail}".strip()) from e
	except (URLError, TimeoutError, ValueError) as e:
		raise MetaAPIError(str(e)) from e


def _pages(path, params, version, limit):
	"""Follow Graph API pagination until `limit` items."""
	url, items = f"{GRAPH}/{version}/{path}", []
	params = {**params, "limit": min(limit, 50)}
	while url and len(items) < limit:
		data = _get(url, params)
		items += data.get("data", [])
		url = data.get("paging", {}).get("next")
		params = {}  # the "next" URL already carries every parameter
	return items[:limit]


def _date(value):
	# Graph API format: 2026-09-30T14:03:11+0000
	return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


# ---------- Facebook ----------

FB_FIELDS = ("id,message,created_time,permalink_url,status_type,"
	"attachments{media_type,media,subattachments{media_type,media}}")


def _fb_images(post):
	urls, video = [], False
	for att in post.get("attachments", {}).get("data", []):
		subs = att.get("subattachments", {}).get("data", [])
		for item in subs or [att]:
			video = video or item.get("media_type") == "video"
			src = item.get("media", {}).get("image", {}).get("src")
			if src:
				urls.append(src)
	return urls[:MAX_IMAGES], video


def parse_facebook(raw_posts):
	posts = []
	for p in raw_posts:
		images, video = _fb_images(p)
		text = (p.get("message") or "").strip()
		if not text and not images:
			continue  # e.g. "X updated their cover photo" with nothing to show
		posts.append(SocialPost("facebook", p["id"], text, _date(p["created_time"]),
			p.get("permalink_url", ""), images, video))
	return posts


def fetch_facebook(page_id, token, version, limit=50):
	return parse_facebook(_pages(f"{page_id}/posts", {"fields": FB_FIELDS, "access_token": token}, version, limit))


# ---------- Instagram (professional account linked to the Page) ----------

IG_FIELDS = ("id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,"
	"children{media_type,media_url,thumbnail_url}")


def instagram_account_id(page_id, token, version):
	data = _get(f"{GRAPH}/{version}/{page_id}", {"fields": "instagram_business_account", "access_token": token})
	account = data.get("instagram_business_account")
	return account["id"] if account else None


def _ig_image(item):
	if item.get("media_type") == "VIDEO":
		return item.get("thumbnail_url")
	return item.get("media_url")


def parse_instagram(raw_posts):
	posts = []
	for p in raw_posts:
		children = p.get("children", {}).get("data", [])
		items = children or [p]
		images = [u for u in (_ig_image(i) for i in items) if u][:MAX_IMAGES]
		video = any(i.get("media_type") == "VIDEO" for i in items)
		text = (p.get("caption") or "").strip()
		if not text and not images:
			continue
		posts.append(SocialPost("instagram", p["id"], text, _date(p["timestamp"]), p.get("permalink", ""),
			images, video))
	return posts


def fetch_instagram(ig_user_id, token, version, limit=50):
	return parse_instagram(_pages(f"{ig_user_id}/media", {"fields": IG_FIELDS, "access_token": token}, version, limit))


# ---------- helpers used by the importer ----------

def comparable_text(text):
	"""Lower-case words without accents, hashtags, emoji or punctuation – to spot the same post on both networks."""
	text = unicodedata.normalize("NFKD", text.lower())
	text = "".join(c for c in text if not unicodedata.combining(c))
	text = re.sub(r"#\w+", " ", text)
	return " ".join(re.findall(r"[a-z0-9]+", text))[:200]


def download(url, max_bytes=20 * 1024 * 1024):
	try:
		with urlopen(Request(url, headers={"User-Agent": "gmfuneraire-site"}), timeout=TIMEOUT) as r:
			data = r.read(max_bytes + 1)
	except (HTTPError, URLError, TimeoutError) as e:
		raise MetaAPIError(f"image: {e}") from e
	if len(data) > max_bytes:
		raise MetaAPIError("image trop lourde")
	return data
