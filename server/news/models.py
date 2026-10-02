from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator, slugify


class Post(models.Model):
	class Source(models.TextChoices):
		SITE = "site", "Site (écrit ici)"
		FACEBOOK = "facebook", "Facebook"
		INSTAGRAM = "instagram", "Instagram"

	source = models.CharField("origine", max_length=10, choices=Source.choices, default=Source.SITE)
	external_id = models.CharField("identifiant Facebook/Instagram", max_length=100, blank=True, editable=False)
	title = models.CharField("titre", max_length=200, blank=True,
		help_text="Laissé vide : la première phrase du texte est utilisée.")
	slug = models.SlugField("adresse de la page", max_length=120, unique=True, blank=True)
	text = models.TextField("texte", blank=True)
	published_at = models.DateTimeField("date", default=timezone.now)
	permalink = models.URLField("lien vers la publication d’origine", max_length=500, blank=True)
	is_video = models.BooleanField("contient une vidéo", default=False,
		help_text="La vidéo n’est pas copiée : un lien vers Facebook/Instagram est affiché.")
	is_published = models.BooleanField("publié", default=True)
	locked = models.BooleanField("ne plus mettre à jour automatiquement", default=False,
		help_text="Coché automatiquement quand vous modifiez une publication importée : "
			"l’import quotidien ne touchera plus ni le texte, ni la visibilité.")
	created_at = models.DateTimeField("ajouté le", auto_now_add=True)
	updated_at = models.DateTimeField("modifié le", auto_now=True)

	class Meta:
		verbose_name = "actualité"
		verbose_name_plural = "actualités"
		ordering = ["-published_at"]
		constraints = [
			models.UniqueConstraint(fields=["source", "external_id"], condition=~models.Q(external_id=""),
				name="unique_social_post"),
		]

	def __str__(self):
		return self.display_title

	@property
	def display_title(self):
		if self.title:
			return self.title
		first_line = (self.text.strip().splitlines() or [""])[0]
		first_sentence = first_line.split(". ")[0].strip()
		return Truncator(first_sentence).chars(90) or f"Publication du {self.published_at:%d/%m/%Y}"

	def get_absolute_url(self):
		return reverse("news:detail", args=[self.slug])

	def save(self, *args, **kwargs):
		if not self.slug:
			base = slugify(self.display_title)[:100] or "actualite"
			slug, n = base, 2
			while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
				slug, n = f"{base}-{n}", n + 1
			self.slug = slug
		super().save(*args, **kwargs)


class PostImage(models.Model):
	post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images", verbose_name="actualité")
	image = models.ImageField("image", upload_to="actualites/%Y/", width_field="width", height_field="height")
	width = models.PositiveIntegerField(default=0, editable=False)
	height = models.PositiveIntegerField(default=0, editable=False)
	order = models.PositiveSmallIntegerField("ordre", default=0)

	class Meta:
		verbose_name = "image"
		verbose_name_plural = "images"
		ordering = ["order", "pk"]

	def __str__(self):
		return f"Image {self.order} – {self.post}"
