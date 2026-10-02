from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
	# hidden from humans by CSS; bots that fill it in are ignored
	website = forms.CharField(required=False, label="Ne pas remplir")

	class Meta:
		model = Comment
		fields = ["author_name", "author_email", "message", "visibility"]
		labels = {
			"author_name": "Votre nom",
			"author_email": "Votre e-mail (facultatif)",
			"message": "Votre message",
			"visibility": "Qui peut lire ce message ?",
		}
		help_texts = {
			"author_email": "Jamais affiché. Pour un message privé, il permet à la famille de vous répondre.",
		}
		widgets = {
			"visibility": forms.RadioSelect,
			"message": forms.Textarea(attrs={"rows": 6, "maxlength": 3000}),
		}

	def __init__(self, *args, memorial, **kwargs):
		super().__init__(*args, **kwargs)
		self.memorial = memorial
		choices = [
			(Comment.Visibility.PUBLIC, "Tout le monde – publié sur cette page après validation"),
			(Comment.Visibility.PRIVATE, "Uniquement la famille – envoyé par e-mail, jamais publié"),
		]
		if not memorial.family_email_list:
			choices = choices[:1]
		self.fields["visibility"].choices = choices
		self.fields["visibility"].initial = Comment.Visibility.PUBLIC

	def clean_message(self):
		message = self.cleaned_data["message"].strip()
		if len(message) > 3000:
			raise forms.ValidationError("Votre message est trop long (3000 caractères maximum).")
		return message

	@property
	def is_spam(self):
		return bool(self.data.get("website"))
