"""Delete photo files from disk when their database row goes (message purged, refused, notice deleted…).

Django removes the row but leaves the file behind; for private messages that would defeat the 30-day deletion."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CommentPhoto


@receiver(post_delete, sender=CommentPhoto)
def delete_photo_file(sender, instance, **kwargs):
	if instance.image:
		instance.image.delete(save=False)
