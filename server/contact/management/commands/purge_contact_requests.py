"""Delete contact requests older than CONTACT_REQUEST_RETENTION_DAYS (3 years, as in the privacy policy). Run daily."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from contact.models import ContactRequest


class Command(BaseCommand):
	help = "Supprime les demandes de contact reçues depuis plus de CONTACT_REQUEST_RETENTION_DAYS jours."

	def handle(self, *args, **options):
		cutoff = timezone.now() - timedelta(days=settings.CONTACT_REQUEST_RETENTION_DAYS)
		deleted, _ = ContactRequest.objects.filter(created_at__lt=cutoff).delete()
		self.stdout.write(f"{deleted} demande(s) de contact supprimée(s).")
