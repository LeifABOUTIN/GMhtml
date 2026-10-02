"""Daily import of the agency's Facebook and Instagram posts into the Actualités section (cron, see deploy/gm.cron)."""

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError

from news import social
from news.importer import sync_source
from news.models import Post


class Command(BaseCommand):
	help = "Importe les dernières publications Facebook et Instagram dans les actualités du site."

	def add_arguments(self, parser):
		parser.add_argument("--limit", type=int, default=50, help="Nombre de publications lues par réseau (50).")

	def handle(self, *args, limit, **options):
		page_id, token, version = settings.META_PAGE_ID, settings.META_PAGE_TOKEN, settings.META_GRAPH_VERSION
		if not (page_id and token):
			self.stdout.write("Import non configuré (META_PAGE_ID / META_PAGE_TOKEN vides) : rien à faire.")
			return

		errors = []
		try:
			self.report("Facebook", sync_source(Post.Source.FACEBOOK,
				social.fetch_facebook(page_id, token, version, limit)))
		except social.MetaAPIError as e:
			errors.append(f"Facebook : {e}")

		if settings.META_IMPORT_INSTAGRAM:
			try:
				ig_id = settings.META_INSTAGRAM_ID or social.instagram_account_id(page_id, token, version)
				if not ig_id:
					errors.append("Instagram : aucun compte Instagram professionnel n’est relié à la page Facebook.")
				else:
					self.report("Instagram", sync_source(Post.Source.INSTAGRAM,
						social.fetch_instagram(ig_id, token, version, limit)))
			except social.MetaAPIError as e:
				errors.append(f"Instagram : {e}")

		if errors:
			self.alert(errors)
			raise CommandError(" | ".join(errors))

	def report(self, network, stats):
		summary = ", ".join(f"{n} {label}" for label, n in stats.items()) or "rien de nouveau"
		self.stdout.write(f"{network} : {summary}")

	def alert(self, errors):
		"""Most failures mean the access token was revoked (password change, admin removed…): tell a human."""
		if not settings.ADMIN_EMAILS:
			return
		body = ("L’import automatique des publications Facebook/Instagram vers la page Actualités a échoué :\n\n"
			+ "\n".join(f"- {e}" for e in errors)
			+ "\n\nSi le message parle de jeton (token) ou de session, il faut générer un nouveau "
			"META_PAGE_TOKEN (voir server/README.md, section « Actualités »).\n")
		try:
			EmailMessage("Site GM – échec de l’import Facebook/Instagram", body, to=settings.ADMIN_EMAILS).send()
		except Exception:
			pass  # the CommandError below still ends up in the cron log
