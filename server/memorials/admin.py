from django.contrib import admin, messages
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib.auth.models import Group

from .emails import send_private_comment
from .models import CeremonyStep, Comment, Memorial

# keep the admin to what the staff actually use (Google login is configured in settings)
for model in (Group, EmailAddress, SocialAccount, SocialApp, SocialToken):
	admin.site.unregister(model)


class CeremonyStepInline(admin.TabularInline):
	model = CeremonyStep
	fields = ["order", "title", "starts_at", "place", "address", "details"]
	extra = 1
	verbose_name_plural = "étapes de la cérémonie (une ligne par étape, avec l’adresse pour l’itinéraire)"


@admin.register(Memorial)
class MemorialAdmin(admin.ModelAdmin):
	inlines = [CeremonyStepInline]
	list_display = ["full_name", "death_date", "is_published", "pending_count", "view_link", "qr_link"]
	list_filter = ["is_published", "comments_open"]
	search_fields = ["first_name", "last_name", "maiden_name"]
	date_hierarchy = "death_date"
	readonly_fields = ["photo_preview", "qr_tools", "created_at", "updated_at"]
	actions = ["publish", "unpublish"]
	fieldsets = [
		("Défunt", {"fields": [("first_name", "last_name"), "maiden_name", ("birth_date", "death_date"), "city",
			"photo", "photo_preview"]}),
		("Avis", {"fields": ["announcement", "ceremony"]}),
		("Famille", {"fields": ["family_emails"]}),
		("Publication", {"fields": ["is_published", "comments_open", "slug", ("created_at", "updated_at")]}),
		("QR code pour la cérémonie", {"fields": ["qr_tools"]}),
	]

	def get_queryset(self, request):
		return super().get_queryset(request).annotate(
			_pending=Count("comments", filter=Q(comments__status=Comment.Status.PENDING,
				comments__visibility=Comment.Visibility.PUBLIC))
		)

	@admin.display(description="nom")
	def full_name(self, obj):
		return obj.full_name

	@admin.display(description="messages à valider", ordering="_pending")
	def pending_count(self, obj):
		if not obj._pending:
			return "–"
		url = f"../comment/?memorial__id__exact={obj.pk}&status__exact=pending"
		return format_html('<a href="{}"><b>{}</b></a>', url, obj._pending)

	@admin.display(description="page")
	def view_link(self, obj):
		if not obj.is_published:
			return "non publié"
		return format_html('<a href="{}" target="_blank">voir ↗</a>', obj.get_absolute_url())

	@admin.display(description="QR code")
	def qr_link(self, obj):
		return format_html('<a href="{}" target="_blank">imprimer ↗</a>', reverse("memorials:qr", args=[obj.slug]))

	@admin.display(description="QR code")
	def qr_tools(self, obj):
		if not obj.pk:
			return "Disponible après l’enregistrement de l’avis."
		warning = "" if obj.is_published else (
			"<p><b>Attention :</b> l’avis n’est pas encore publié, le QR code mènera à une page introuvable "
			"tant que « publié » n’est pas coché.</p>")
		return format_html(
			'{}<p>Le QR code ouvre la page de l’avis, où les proches peuvent laisser un message.</p>'
			'<p><a href="{}" target="_blank">Affiche A4 ↗</a> · <a href="{}" target="_blank">Cartes à emporter ↗</a>'
			' · <a href="{}">Télécharger le QR code seul (SVG)</a></p>',
			mark_safe(warning),
			reverse("memorials:qr", args=[obj.slug]),
			reverse("memorials:qr", args=[obj.slug]) + "?format=cartes",
			reverse("memorials:qr_download", args=[obj.slug]),
		)

	@admin.display(description="aperçu")
	def photo_preview(self, obj):
		if not obj.photo:
			return "–"
		return format_html('<img src="{}" style="max-height:200px;border-radius:8px" />', obj.photo.url)

	@admin.action(description="Publier les avis sélectionnés")
	def publish(self, request, queryset):
		queryset.update(is_published=True)

	@admin.action(description="Masquer les avis sélectionnés")
	def unpublish(self, request, queryset):
		queryset.update(is_published=False)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
	list_display = ["created_at", "memorial", "author_name", "visibility", "status", "excerpt"]
	list_filter = ["status", "visibility", "memorial"]
	search_fields = ["author_name", "memorial__first_name", "memorial__last_name"]
	list_select_related = ["memorial"]
	actions = ["approve", "reject", "resend"]

	def has_add_permission(self, request):
		return False  # messages come from visitors

	def get_fields(self, request, obj=None):
		fields = ["memorial", "author_name", "author_email", "visibility", "status", "created_at"]
		# private messages are for the family only: admins see that one was sent, not its content
		return fields if obj and obj.is_private else fields[:3] + ["message"] + fields[3:]

	def get_readonly_fields(self, request, obj=None):
		return ["memorial", "author_name", "author_email", "visibility", "created_at"] + (
			["status"] if obj and obj.is_private else []
		)

	@admin.display(description="message")
	def excerpt(self, obj):
		if obj.is_private:
			return format_html("<i>{}</i>", "message privé – transmis à la famille")
		return obj.message[:80] + ("…" if len(obj.message) > 80 else "")

	@admin.action(description="✔ Publier les messages sélectionnés")
	def approve(self, request, queryset):
		n = queryset.filter(visibility=Comment.Visibility.PUBLIC).update(status=Comment.Status.APPROVED)
		self.message_user(request, f"{n} message(s) publié(s).")

	@admin.action(description="✖ Refuser les messages sélectionnés")
	def reject(self, request, queryset):
		n = queryset.filter(visibility=Comment.Visibility.PUBLIC).update(status=Comment.Status.REJECTED)
		self.message_user(request, f"{n} message(s) refusé(s).")

	@admin.action(description="↻ Renvoyer à la famille (messages privés en échec)")
	def resend(self, request, queryset):
		sent = failed = 0
		for comment in queryset.filter(visibility=Comment.Visibility.PRIVATE, status=Comment.Status.FAILED):
			if send_private_comment(comment):
				comment.status = Comment.Status.SENT
				comment.save(update_fields=["status"])
				sent += 1
			else:
				failed += 1
		self.message_user(request, f"{sent} renvoyé(s), {failed} en échec.",
			messages.WARNING if failed else messages.SUCCESS)
