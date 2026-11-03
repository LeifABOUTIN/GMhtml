import json
from pathlib import Path

from datetime import datetime

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import AdminDateWidget, AdminTimeWidget
from django.forms.models import BaseInlineFormSet
from django.utils import timezone
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib.auth.models import Group

from .emails import send_private_comment, send_qr_to_family
from .models import CeremonyStep, Comment, CommentPhoto, Memorial, Place, searchable

# keep the admin to what the staff actually use (Google login is configured in settings)
for model in (Group, EmailAddress, SocialAccount, SocialApp, SocialToken):
	admin.site.unregister(model)
admin.site.enable_nav_sidebar = False  # few models: the pages stay centred without the side menu

_get_app_list = admin.site.get_app_list


def get_app_list(request, app_label=None):
	"""« Avis de décès » first: it's what the staff use most."""
	return sorted(_get_app_list(request, app_label), key=lambda app: app["app_label"] != "memorials")


admin.site.get_app_list = get_app_list


STEP_TITLES = Path(__file__).resolve().parent / "data" / "steps.json"


class StepTitleInput(forms.TextInput):
	"""Free text with the usual step names suggested as you type (memorials/data/steps.json)."""

	def render(self, name, value, attrs=None, renderer=None):
		# one shared list id: rows added with "Ajouter" are copies whose ids get renumbered, the list's must not
		list_id = "gm-step-titles"
		html = super().render(name, value, {**(attrs or {}), "list": list_id, "autocomplete": "off"}, renderer)
		options = "".join(format_html('<option value="{}">', title)
			for title in json.loads(STEP_TITLES.read_text(encoding="utf-8")))
		return mark_safe(f'{html}<datalist id="{list_id}">{options}</datalist>')


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
	list_display = ["title", "name", "address"]
	search_fields = ["search"]  # see get_search_results
	fields = ["title", "name", "address"]

	def get_search_results(self, request, queryset, search_term):
		# every word typed must appear in the title, lieu or adresse, ignoring case and accents
		for word in searchable(search_term).split():
			queryset = queryset.filter(search__contains=word)
		return queryset, False

	def get_urls(self):
		return [path("<int:pk>/json/", self.admin_site.admin_view(self.place_json), name="memorials_place_json"),
			*super().get_urls()]

	def place_json(self, request, pk):
		"""Lieu + adresse of one place, for place_picker.js."""
		place = get_object_or_404(Place, pk=pk)
		return JsonResponse({"name": place.name, "address": place.address})


class CeremonyStepForm(forms.ModelForm):
	"""Date and time apart: the date is entered on the first step only, the others just give a time."""

	day = forms.DateField(label="date de la cérémonie", required=False, widget=AdminDateWidget,
		help_text="Sur la première étape seulement : les suivantes ont lieu le même jour.")
	time = forms.TimeField(label="heure", required=False, widget=AdminTimeWidget)

	class Meta:
		model = CeremonyStep
		exclude = ["starts_at"]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance.starts_at:
			local = timezone.localtime(self.instance.starts_at)
			self.initial.update(day=local.date(), time=local.time().replace(second=0, microsecond=0))


class CeremonyStepFormSet(BaseInlineFormSet):
	def clean(self):
		super().clean()
		steps = [f for f in self.forms if f.has_changed() or f.instance.pk]
		steps = [f for f in steps if not (self.can_delete and self._should_delete_form(f)) and hasattr(f, "cleaned_data")]
		if not steps:
			return
		first = steps[0]
		day, time = first.cleaned_data.get("day"), first.cleaned_data.get("time")
		if time and not day:
			first.add_error("day", "Indiquez la date de la cérémonie sur la première étape.")
		if day and not time:
			first.add_error("time", "Indiquez l’heure de la première étape.")
		for form in steps:
			# the day of a later step is never typed (its field is hidden): always the first step's
			step_time = form.cleaned_data.get("time")
			if step_time and not day:
				if form is not first:
					form.add_error("time", "Indiquez d’abord la date sur la première étape.")
				continue
			form.instance.starts_at = timezone.make_aware(datetime.combine(day, step_time)) if step_time else None


class CeremonyStepInline(admin.StackedInline):
	"""One block per step (a table row was wider than the screen)."""

	model = CeremonyStep
	form = CeremonyStepForm
	formset = CeremonyStepFormSet
	fields = [("title", "order"), ("day", "time"), "saved_place", ("place", "address"), "details"]
	autocomplete_fields = ["saved_place"]  # type a few letters of the name, the town or the street
	extra = 1
	verbose_name_plural = "étapes de la cérémonie (choisissez un lieu enregistré ou tapez-en un nouveau)"

	class Media:
		# listed with jQuery and jquery.init.js so Django puts the picker after them (it uses django.jQuery)
		js = ["admin/js/vendor/jquery/jquery.min.js", "admin/js/jquery.init.js", "memorials/place_picker.js"]

	def formfield_for_dbfield(self, db_field, request, **kwargs):
		if db_field.name == "title":
			kwargs["widget"] = StepTitleInput()
		return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Memorial)
class MemorialAdmin(admin.ModelAdmin):
	inlines = [CeremonyStepInline]
	list_display = ["full_name", "death_date", "is_published", "view_link", "qr_link"]
	list_filter = ["is_published"]  # "comments_open": messages switched off
	search_fields = ["first_name", "last_name", "maiden_name"]
	date_hierarchy = "death_date"
	readonly_fields = ["qr_tools", "created_at", "updated_at"]
	actions = ["publish", "unpublish", "send_qr"]
	fieldsets = [
		("Défunt", {"fields": [("first_name", "last_name"), "maiden_name", ("birth_date", "death_date"), "city"]}),  # "photo", "photo_preview": pictures switched off
		("Avis", {"fields": ["announcement", "ceremony", "faire_part"]}),
		("Famille", {"fields": ["family_emails"]}),
		("Publication", {"fields": ["is_published", "slug", ("created_at", "updated_at")]}),
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
		if obj.family_email_list:
			send = format_html('<p><button type="submit" name="_send_qr" class="button">'
				'Enregistrer et envoyer le lien + QR code à la famille ({})</button></p>', ", ".join(obj.family_email_list))
		else:
			send = mark_safe("<p>Ajoutez les e-mails de la famille (plus haut) pour leur envoyer le lien et le QR code.</p>")
		return format_html(
			'{}<p>Le QR code ouvre la page de l’avis.</p>'
			'<p><a href="{}" target="_blank">Affiche A4 ↗</a> · <a href="{}" target="_blank">Cartes à emporter ↗</a>'
			' · <a href="{}">Télécharger le QR code seul (SVG)</a></p>{}',
			mark_safe(warning),
			reverse("memorials:qr", args=[obj.slug]),
			reverse("memorials:qr", args=[obj.slug]) + "?format=cartes",
			reverse("memorials:qr_download", args=[obj.slug]),
			send,
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

	@admin.action(description="✉ Envoyer le lien et le QR code à la famille")
	def send_qr(self, request, queryset):
		for memorial in queryset:
			self._send_qr(request, memorial)

	def response_change(self, request, obj):
		# "Enregistrer et envoyer…" button in the QR code box: the notice is saved, then sent
		if "_send_qr" in request.POST:
			self._send_qr(request, obj)
			return HttpResponseRedirect(request.path)
		return super().response_change(request, obj)

	def _send_qr(self, request, memorial):
		if not memorial.is_published:
			self.message_user(request, f"{memorial.full_name} : publiez l’avis avant d’envoyer le lien à la famille.",
				messages.ERROR)
		elif not memorial.family_email_list:
			self.message_user(request, f"{memorial.full_name} : aucun e-mail de la famille.", messages.WARNING)
		else:
			sent, failed = send_qr_to_family(memorial)
			if failed:
				self.message_user(request, f"{memorial.full_name} : {sent} e-mail(s) envoyé(s), {failed} en échec.",
					messages.WARNING)
			else:
				self.message_user(request, f"{memorial.full_name} : lien et QR code envoyés à {sent} adresse(s).")


class CommentPhotoInline(admin.TabularInline):
	model = CommentPhoto
	fields = ["preview"]
	readonly_fields = ["preview"]
	extra = 0
	can_delete = True  # remove one unsuitable photo but keep the message
	verbose_name_plural = "photos jointes (supprimez celles qui ne conviennent pas avant de publier)"

	def has_add_permission(self, request, obj=None):
		return False

	@admin.display(description="photo")
	def preview(self, obj):
		return format_html('<a href="{0}" target="_blank"><img src="{0}" style="max-height:220px;border-radius:6px" /></a>',
			obj.image.url)


# @admin.register(Comment)  # condolence messages switched off for now
class CommentAdmin(admin.ModelAdmin):
	list_display = ["created_at", "memorial", "author_name", "visibility", "status", "excerpt", "photo_count"]
	list_filter = ["status", "visibility", "memorial"]
	search_fields = ["author_name", "memorial__first_name", "memorial__last_name"]
	list_select_related = ["memorial"]
	actions = ["approve", "reject", "resend"]

	def has_add_permission(self, request):
		return False  # messages come from visitors

	def get_queryset(self, request):
		return super().get_queryset(request).annotate(_photos=Count("photos"))

	def get_inlines(self, request, obj):
		# private photos are for the family only, like the private text
		return [] if obj is None or obj.is_private else [CommentPhotoInline]

	@admin.display(description="photos", ordering="_photos")
	def photo_count(self, obj):
		return obj._photos or "–"

	def get_fields(self, request, obj=None):
		fields = ["memorial", "author_name", "relationship", "author_email", "visibility", "status", "created_at"]
		# private messages are for the family only: admins see that one was sent, not its content
		return fields if obj and obj.is_private else fields[:4] + ["message"] + fields[4:]

	def get_readonly_fields(self, request, obj=None):
		return ["memorial", "author_name", "relationship", "author_email", "visibility", "created_at"] + (
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
