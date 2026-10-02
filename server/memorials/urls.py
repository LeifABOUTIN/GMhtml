from django.urls import path

from . import views

app_name = "memorials"
urlpatterns = [
	path("", views.memorial_list, name="list"),
	path("<slug:slug>/", views.memorial_detail, name="detail"),
]
