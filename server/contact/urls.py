from django.urls import path

from . import views

app_name = "contact"
urlpatterns = [
	path("envoyer/", views.submit, name="submit"),
]
