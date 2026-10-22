from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

admin.site.site_header = "Pompes Funèbres et Marbrerie GM – Administration"
admin.site.site_title = "GM – Administration"
admin.site.index_title = "Gestion du site"
admin.site.enable_nav_sidebar = False  # more room for the (larger) lists; the header and breadcrumbs lead everywhere

to_admin_login = RedirectView.as_view(pattern_name="admin:login", query_string=True)

urlpatterns = [
	path("admin/", admin.site.urls),
	# allauth's own login / sign-up pages are not used: the admin login page has the Google button
	path("accounts/login/", to_admin_login),
	path("accounts/signup/", to_admin_login),
	path("accounts/3rdparty/signup/", to_admin_login),
	path("accounts/", include("allauth.urls")),
	path("avis-de-deces/", include("memorials.urls")),
	path("actualites/", include("news.urls")),
	path("contact/", include("contact.urls")),
]

if settings.DEBUG:
	# In development Django also serves the static website and uploads;
	# in production nginx does it (see deploy/nginx.conf).

	def site_file(request, path=""):
		if path.split("/")[0] in ("server", ".git") or path.startswith("."):
			raise Http404
		return serve(request, path or "index.html", document_root=settings.SITE_DIR)

	def media_file(request, path):
		if path.startswith("messages/prive/"):
			raise Http404  # same rule as nginx in production
		return serve(request, path, document_root=settings.MEDIA_ROOT)

	urlpatterns += [
		re_path(r"^media/(?P<path>.*)$", media_file),
		path("", site_file),
		re_path(r"^(?P<path>.+)$", site_file),
	]
