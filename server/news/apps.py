from django.apps import AppConfig


class NewsConfig(AppConfig):
	name = "news"
	verbose_name = "Actualités"
	default_auto_field = "django.db.models.BigAutoField"

	def ready(self):
		from . import signals  # noqa: F401
