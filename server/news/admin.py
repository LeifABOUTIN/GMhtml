from django.contrib import admin
from django.utils.html import format_html

from .models import Post, PostImage


class PostImageInline(admin.TabularInline):
	model = PostImage
	fields = ["preview", "image", "order"]
	readonly_fields = ["preview"]
	extra = 0

	@admin.display(description="aperçu")
	def preview(self, obj):
		if not obj.pk or not obj.image:
			return "–"
		return format_html('<img src="{}" style="max-height:120px;border-radius:6px" />', obj.image.url)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
	inlines = [PostImageInline]
	list_display = ["thumb", "display_title", "source", "published_at", "is_published", "locked", "view_link"]
	list_display_links = ["thumb", "display_title"]
	list_filter = ["source", "is_published", "locked"]
	search_fields = ["title", "text"]
	date_hierarchy = "published_at"
	actions = ["publish", "hide"]
	readonly_fields = ["source", "original_link", "created_at", "updated_at"]
	fieldsets = [
		(None, {"fields": ["title", "text", "published_at", "is_published"]}),
		("Origine", {"fields": ["source", "original_link", "is_video", "locked", "slug", ("created_at", "updated_at")]}),
	]

	def get_queryset(self, request):
		return super().get_queryset(request).prefetch_related("images")

	@admin.display(description="")
	def thumb(self, obj):
		first = next(iter(obj.images.all()), None)
		if not first:
			return "–"
		return format_html('<img src="{}" style="height:48px;width:64px;object-fit:cover;border-radius:4px" />',
			first.image.url)

	@admin.display(description="titre")
	def display_title(self, obj):
		return obj.display_title

	@admin.display(description="page")
	def view_link(self, obj):
		if not obj.is_published:
			return "masqué"
		return format_html('<a href="{}" target="_blank">voir ↗</a>', obj.get_absolute_url())

	@admin.display(description="publication d’origine")
	def original_link(self, obj):
		if not obj.permalink:
			return "–"
		return format_html('<a href="{0}" target="_blank">{0}</a>', obj.permalink)

	def save_model(self, request, obj, form, change):
		# an imported post edited here must not be overwritten by tomorrow's import
		if change and obj.source != Post.Source.SITE and {"title", "text", "is_published", "published_at"} & set(
				form.changed_data):
			obj.locked = True
		super().save_model(request, obj, form, change)

	@admin.action(description="Publier les actualités sélectionnées")
	def publish(self, request, queryset):
		queryset.update(is_published=True, locked=True)

	@admin.action(description="Masquer les actualités sélectionnées")
	def hide(self, request, queryset):
		queryset.update(is_published=False, locked=True)
