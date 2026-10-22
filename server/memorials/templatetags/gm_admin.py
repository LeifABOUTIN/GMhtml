"""Admin home page: what needs attention (no e-mail is required to notice new things)."""

from django import template
from django.urls import reverse

from contact.models import ContactRequest
from memorials.models import Comment

register = template.Library()


@register.simple_tag
def todo_items():
	items = [
		(ContactRequest.objects.filter(status=ContactRequest.Status.NEW).count(),
			"nouvelle(s) demande(s) de contact",
			reverse("admin:contact_contactrequest_changelist") + "?status__exact=new"),
		(Comment.objects.filter(visibility=Comment.Visibility.PUBLIC, status=Comment.Status.PENDING).count(),
			"message(s) de condoléances à valider",
			reverse("admin:memorials_comment_changelist") + "?status__exact=pending"),
		(Comment.objects.filter(visibility=Comment.Visibility.PRIVATE, status=Comment.Status.FAILED).count(),
			"message(s) privé(s) non transmis à la famille (à renvoyer)",
			reverse("admin:memorials_comment_changelist") + "?status__exact=failed"),
	]
	return [{"count": n, "label": label, "url": url} for n, label, url in items if n]
