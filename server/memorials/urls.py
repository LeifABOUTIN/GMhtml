from django.urls import path

from . import views

app_name = "memorials"
urlpatterns = [
	path("", views.memorial_list, name="list"),
	path("<slug:slug>/", views.memorial_detail, name="detail"),
	# no file extension on purpose: nginx serves *.svg/*.png itself and would never pass them to Django
	path("<slug:slug>/qr/", views.qr_print, name="qr"),
	path("<slug:slug>/qr/telecharger/", views.qr_download, name="qr_download"),
]
