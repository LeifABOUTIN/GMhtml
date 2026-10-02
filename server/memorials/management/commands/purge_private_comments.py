"""Delete private messages once they have been delivered to the family (run daily from cron)."""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from memorials.models import Comment


class Command(BaseCommand):
	help = "Supprime les messages privés transmis depuis plus de PRIVATE_COMMENT_RETENTION_DAYS jours."

	def handle(self, *args, **options):
		cutoff = timezone.now() - timedelta(days=settings.PRIVATE_COMMENT_RETENTION_DAYS)
		deleted, _ = Comment.objects.filter(
			visibility=Comment.Visibility.PRIVATE, status=Comment.Status.SENT, created_at__lt=cutoff
		).delete()
		self.stdout.write(f"{deleted} message(s) privé(s) supprimé(s).")
