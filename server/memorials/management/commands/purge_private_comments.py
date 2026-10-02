"""Delete messages that no longer need to be kept (run daily from cron).

The command keeps its original name so the existing cron line on the server keeps working.
- private messages delivered to the family: PRIVATE_COMMENT_RETENTION_DAYS after they were received
- private messages that could not be delivered: same delay (admins can use "Renvoyer" until then)
- public messages refused by an admin: REJECTED_COMMENT_RETENTION_DAYS after they were received
Messages waiting for approval and published messages are never deleted by this command.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from memorials.models import Comment


class Command(BaseCommand):
	help = "Supprime les messages privés transmis ou en échec, et les messages refusés, après leur délai de conservation."

	def handle(self, *args, **options):
		now = timezone.now()
		private_cutoff = now - timedelta(days=settings.PRIVATE_COMMENT_RETENTION_DAYS)
		rejected_cutoff = now - timedelta(days=settings.REJECTED_COMMENT_RETENTION_DAYS)

		private, _ = Comment.objects.filter(
			visibility=Comment.Visibility.PRIVATE,
			status__in=[Comment.Status.SENT, Comment.Status.FAILED],
			created_at__lt=private_cutoff,
		).delete()
		rejected, _ = Comment.objects.filter(
			status=Comment.Status.REJECTED, created_at__lt=rejected_cutoff,
		).delete()
		self.stdout.write(f"{private} message(s) privé(s) et {rejected} message(s) refusé(s) supprimé(s).")
