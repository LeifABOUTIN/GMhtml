from django.db import models


class ContactRequest(models.Model):
	"""A request sent with the contact form (pages/contact.html)."""

	class Reason(models.TextChoices):
		QUOTE = "devis", "Devis gratuit"
		INFO = "infos", "Informations"

	class Status(models.TextChoices):
		NEW = "new", "Nouvelle"
		HANDLED = "handled", "Traitée"

	reason = models.CharField("demande", max_length=10, choices=Reason.choices)
	name = models.CharField("nom", max_length=150)
	email = models.EmailField("e-mail", blank=True)
	phone = models.CharField("téléphone", max_length=30, blank=True)
	message = models.TextField("message", blank=True)
	status = models.CharField("statut", max_length=10, choices=Status.choices, default=Status.NEW)
	notes = models.TextField("notes internes", blank=True, help_text="Visible uniquement dans l’administration.")
	created_at = models.DateTimeField("reçue le", auto_now_add=True)
	handled_at = models.DateTimeField("traitée le", null=True, blank=True)

	class Meta:
		verbose_name = "demande de contact"
		verbose_name_plural = "demandes de contact"
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.name} – {self.get_reason_display()}"

	@property
	def contact(self):
		return self.email or self.phone
