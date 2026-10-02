from urllib.parse import quote_plus
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def split_emails(value):
	return [e.strip() for e in value.replace(";", ",").split(",") if e.strip()]


def validate_email_list(value):
	for email in split_emails(value):
		try:
			validate_email(email)
		except ValidationError:
			raise ValidationError(f"Adresse e-mail invalide : {email}")


class Memorial(models.Model):
	first_name = models.CharField("prénom", max_length=100)
	last_name = models.CharField("nom", max_length=100)
	maiden_name = models.CharField("nom de naissance", max_length=100, blank=True, help_text="Affiché « née … »")
	slug = models.SlugField("adresse de la page", max_length=160, unique=True, blank=True,
		help_text="Générée automatiquement si laissée vide.")
	birth_date = models.DateField("date de naissance", null=True, blank=True)
	death_date = models.DateField("date de décès")
	city = models.CharField("commune", max_length=120, blank=True)
	photo = models.ImageField("photo", upload_to="avis/%Y/", blank=True)
	announcement = models.TextField("texte de l’avis",
		help_text="Texte de l’avis de décès, tel qu’il apparaîtra sur la page.")
	ceremony = models.TextField("informations complémentaires", blank=True,
		help_text="Facultatif : fleurs, dons, « ni fleurs ni couronnes »… Les étapes de la cérémonie "
			"se saisissent dans le tableau « Étapes de la cérémonie » plus bas.")
	family_emails = models.CharField("e-mails de la famille", max_length=500, blank=True,
		validators=[validate_email_list],
		help_text="Reçoivent les messages privés. Plusieurs adresses séparées par des virgules.")
	is_published = models.BooleanField("publié", default=False,
		help_text="Décochez pour masquer la page au public.")
	comments_open = models.BooleanField("messages autorisés", default=True)
	created_at = models.DateTimeField("créé le", auto_now_add=True)
	updated_at = models.DateTimeField("modifié le", auto_now=True)

	class Meta:
		verbose_name = "avis de décès"
		verbose_name_plural = "avis de décès"
		ordering = ["-death_date", "last_name"]

	def __str__(self):
		return self.full_name

	@property
	def full_name(self):
		return f"{self.first_name} {self.last_name}"

	@property
	def family_email_list(self):
		return split_emails(self.family_emails)

	def get_absolute_url(self):
		return reverse("memorials:detail", args=[self.slug])

	@property
	def public_url(self):
		"""Full address of the page, as printed in the QR code."""
		return settings.SITE_URL + self.get_absolute_url()

	def save(self, *args, **kwargs):
		if not self.slug:
			base = slugify(f"{self.first_name} {self.last_name} {self.death_date.year}")[:150]
			slug, n = base, 2
			while Memorial.objects.filter(slug=slug).exclude(pk=self.pk).exists():
				slug, n = f"{base}-{n}", n + 1
			self.slug = slug
		super().save(*args, **kwargs)


class CeremonyStep(models.Model):
	"""One stage of the funeral (levée du corps, cérémonie, inhumation…), with a Google Maps link."""

	memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name="steps", verbose_name="avis")
	title = models.CharField("étape", max_length=120,
		help_text="Ex. : Levée du corps, Cérémonie religieuse, Inhumation, Crémation, Réunion après la cérémonie.")
	starts_at = models.DateTimeField("date et heure", null=True, blank=True)
	place = models.CharField("lieu", max_length=160, blank=True, help_text="Ex. : Église Saint-Germain")
	address = models.CharField("adresse", max_length=255, blank=True,
		help_text="Sert au lien « Itinéraire » vers Google Maps.")
	details = models.CharField("précisions", max_length=255, blank=True,
		help_text="Ex. : dans l’intimité familiale")
	order = models.PositiveSmallIntegerField("ordre", default=0)

	class Meta:
		verbose_name = "étape de la cérémonie"
		verbose_name_plural = "étapes de la cérémonie"
		ordering = ["order", "starts_at", "pk"]

	def __str__(self):
		return self.title

	@property
	def maps_url(self):
		query = ", ".join(part for part in (self.place, self.address) if part)
		if not self.address:
			return ""
		return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)


class Comment(models.Model):
	class Visibility(models.TextChoices):
		PUBLIC = "public", "Public"
		PRIVATE = "private", "Privé (famille uniquement)"

	class Status(models.TextChoices):
		PENDING = "pending", "En attente de validation"
		APPROVED = "approved", "Publié"
		REJECTED = "rejected", "Refusé"
		SENT = "sent", "Transmis à la famille"
		FAILED = "failed", "Échec de l’envoi"

	memorial = models.ForeignKey(Memorial, on_delete=models.CASCADE, related_name="comments", verbose_name="avis")
	author_name = models.CharField("nom", max_length=100)
	author_email = models.EmailField("e-mail", blank=True)
	relationship = models.CharField("lien avec le défunt", max_length=100, blank=True)
	message = models.TextField("message")
	visibility = models.CharField("visibilité", max_length=10, choices=Visibility.choices)
	status = models.CharField("statut", max_length=10, choices=Status.choices)
	created_at = models.DateTimeField("reçu le", auto_now_add=True)

	class Meta:
		verbose_name = "message"
		verbose_name_plural = "messages"
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.author_name} → {self.memorial}"

	@property
	def is_private(self):
		return self.visibility == self.Visibility.PRIVATE


def comment_photo_path(instance, filename):
	# random names: a pending photo can't be found by guessing; private ones live in a folder nginx refuses to serve
	folder = "prive" if instance.comment.is_private else "public"
	return f"messages/{folder}/{uuid4().hex}.jpg"


class CommentPhoto(models.Model):
	MAX_PER_MESSAGE = 3

	comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="photos", verbose_name="message")
	image = models.ImageField("photo", upload_to=comment_photo_path, width_field="width", height_field="height")
	width = models.PositiveIntegerField(default=0, editable=False)
	height = models.PositiveIntegerField(default=0, editable=False)

	class Meta:
		verbose_name = "photo"
		verbose_name_plural = "photos"
		ordering = ["pk"]

	def __str__(self):
		return f"Photo de {self.comment.author_name}"
