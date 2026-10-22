from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import ContactRequest


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
	list_display = ["created_at", "status_badge", "reason", "name", "contact_link", "excerpt"]
	list_display_links = ["created_at", "name"]
	list_filter = ["status", "reason"]
	search_fields = ["name", "email", "phone", "message"]
	date_hierarchy = "created_at"
	actions = ["mark_handled", "mark_new"]
	readonly_fields = ["reason", "name", "email", "phone", "message", "created_at", "handled_at"]
	fields = ["reason", "name", "email", "phone", "message", "created_at", "status", "handled_at", "notes"]

	def has_add_permission(self, request):
		return False  # requests come from the website form

	def save_model(self, request, obj, form, change):
		if "status" in form.changed_data:
			obj.handled_at = timezone.now() if obj.status == ContactRequest.Status.HANDLED else None
		super().save_model(request, obj, form, change)

	@admin.display(description="statut", ordering="status")
	def status_badge(self, obj):
		if obj.status == ContactRequest.Status.NEW:
			return format_html('<b style="color:#8a2b22">{}</b>', obj.get_status_display())
		return obj.get_status_display()

	@admin.display(description="contact")
	def contact_link(self, obj):
		if obj.email:
			return format_html('<a href="mailto:{0}">{0}</a>', obj.email)
		return format_html('<a href="tel:{0}">{0}</a>', obj.phone)

	@admin.display(description="message")
	def excerpt(self, obj):
		return obj.message[:70] + ("…" if len(obj.message) > 70 else "")

	@admin.action(description="✔ Marquer comme traitées")
	def mark_handled(self, request, queryset):
		n = queryset.update(status=ContactRequest.Status.HANDLED, handled_at=timezone.now())
		self.message_user(request, f"{n} demande(s) marquée(s) comme traitée(s).")

	@admin.action(description="Marquer comme nouvelles")
	def mark_new(self, request, queryset):
		queryset.update(status=ContactRequest.Status.NEW, handled_at=None)
