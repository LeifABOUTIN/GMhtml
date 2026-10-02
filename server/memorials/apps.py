from django.apps import AppConfig


class MemorialsConfig(AppConfig):
	name = "memorials"
	verbose_name = "Avis de décès"
	default_auto_field = "django.db.models.BigAutoField"

	def ready(self):
		from . import signals  # noqa: F401  (connects the file-deletion handler)
