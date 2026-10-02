from django import forms
from django.template.defaultfilters import filesizeformat

from gm.images import InvalidImage, normalise_photo

from .models import Comment, CommentPhoto

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # per photo, before resizing (recent phones: 3-8 MB)


class MultipleFileInput(forms.ClearableFileInput):
	allow_multiple_selected = True


class MultipleFileField(forms.FileField):
	"""Several files in one <input type="file" multiple> (pattern from the Django docs)."""

	def __init__(self, *args, **kwargs):
		kwargs.setdefault("widget", MultipleFileInput())
		super().__init__(*args, **kwargs)

	def clean(self, data, initial=None):
		single = super().clean
		if isinstance(data, (list, tuple)):
			return [single(d, initial) for d in data if d]
		return [single(data, initial)] if data else []


class CommentForm(forms.ModelForm):
	# hidden from humans by CSS; bots that fill it in are ignored
	website = forms.CharField(required=False, label="Ne pas remplir")
	photos = MultipleFileField(
		required=False,
		label=f"Photos (facultatif, {CommentPhoto.MAX_PER_MESSAGE} maximum)",
		help_text="Un souvenir partagé avec le défunt. Les photos publiques sont visibles après validation.",
		# listing the formats makes iPhones convert HEIC photos to JPEG before sending
		widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
	)

	class Meta:
		model = Comment
		fields = ["author_name", "relationship", "author_email", "message", "visibility"]
		labels = {
			"author_name": "Votre nom",
			"relationship": "Votre lien avec le défunt (facultatif)",
			"author_email": "Votre e-mail (facultatif)",
			"message": "Votre message",
			"visibility": "Qui peut lire ce message ?",
		}
		help_texts = {
			"author_email": "Jamais affiché. Pour un message privé, il permet à la famille de vous répondre.",
		}
		widgets = {
			"relationship": forms.TextInput(attrs={"placeholder": "Ex. : ami d’enfance, collègue, voisine…"}),
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

	def clean_photos(self):
		files = self.cleaned_data["photos"]
		if len(files) > CommentPhoto.MAX_PER_MESSAGE:
			raise forms.ValidationError(f"{CommentPhoto.MAX_PER_MESSAGE} photos maximum par message.")
		self.processed_photos = []
		for f in files:
			if f.size > MAX_UPLOAD_BYTES:
				raise forms.ValidationError(
					f"« {f.name} » est trop lourde ({filesizeformat(f.size)}, {filesizeformat(MAX_UPLOAD_BYTES)} maximum).")
			try:
				jpeg, _, _ = normalise_photo(f.read())
			except InvalidImage:
				raise forms.ValidationError(f"« {f.name} » n’est pas une photo lisible (formats acceptés : JPEG, PNG, WebP).")
			self.processed_photos.append(jpeg)
		return files

	@property
	def is_spam(self):
		return bool(self.data.get("website"))
