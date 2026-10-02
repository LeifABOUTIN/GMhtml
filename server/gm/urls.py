from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = "Pompes Funèbres et Marbrerie GM – Administration"
admin.site.site_title = "GM – Administration"
admin.site.index_title = "Gestion du site"

urlpatterns = [
	path("admin/", admin.site.urls),
	path("accounts/", include("allauth.urls")),
	path("avis-de-deces/", include("memorials.urls")),
]

if settings.DEBUG:
	# In development Django also serves the static website and uploads;
	# in production nginx does it (see deploy/nginx.conf).

	def site_file(request, path=""):
		if path.split("/")[0] in ("server", ".git") or path.startswith("."):
			raise Http404
		return serve(request, path or "index.html", document_root=settings.SITE_DIR)

	urlpatterns += [
		re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
		path("", site_file),
		re_path(r"^(?P<path>.+)$", site_file),
	]
