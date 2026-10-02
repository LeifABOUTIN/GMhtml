import time

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.safestring import mark_safe

from .emails import notify_moderators, send_private_comment
from .forms import CommentForm
from .models import Comment, CommentPhoto, Memorial
from .qr import qr_svg

RATE_LIMIT = 5  # comments per visitor…
RATE_WINDOW = 10 * 60  # …per 10 minutes


def memorial_list(request):
	memorials = Memorial.objects.filter(is_published=True)
	q = request.GET.get("q", "").strip()
	if q:
		memorials = memorials.filter(
			Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(maiden_name__icontains=q)
		)
	page = Paginator(memorials, 12).get_page(request.GET.get("page"))
	return render(request, "memorials/list.html", {"page": page, "q": q})


def memorial_detail(request, slug):
	memorial = get_object_or_404(Memorial, slug=slug, is_published=True)
	form = CommentForm(request.POST or None, request.FILES or None, memorial=memorial)

	if request.method == "POST" and memorial.comments_open:
		if form.is_spam:
			# pretend it worked so bots learn nothing
			messages.success(request, "Merci, votre message a bien été reçu.")
			return redirect(memorial.get_absolute_url() + "#messages")
		if _rate_limited(request):
			messages.error(request, "Vous avez envoyé plusieurs messages en peu de temps. Merci de réessayer plus tard.")
		elif form.is_valid():
			comment = form.save(commit=False)
			comment.memorial = memorial
			comment.status = Comment.Status.PENDING
			comment.save()
			for jpeg in form.processed_photos:
				CommentPhoto.objects.create(comment=comment, image=ContentFile(jpeg, name="photo.jpg"))
			if comment.is_private:
				comment.status = Comment.Status.SENT if send_private_comment(comment) else Comment.Status.FAILED
				comment.save(update_fields=["status"])
				messages.success(request, "Merci, votre message a été transmis à la famille.")
			else:
				notify_moderators(comment)
				messages.success(request, "Merci, votre message sera publié sur cette page après validation.")
			return redirect(memorial.get_absolute_url() + "#messages")

	public_comments = memorial.comments.filter(
		visibility=Comment.Visibility.PUBLIC, status=Comment.Status.APPROVED
	).order_by("created_at").prefetch_related("photos")
	return render(request, "memorials/detail.html", {
		"memorial": memorial,
		"steps": memorial.steps.all(),
		"comments": public_comments,
		"form": form,
	})


# --- QR code for the ceremony (staff only: works before the page is published) ---

PRINT_FORMATS = {"affiche": "Affiche A4", "cartes": "Cartes à emporter (8 par page)"}


@staff_member_required
def qr_print(request, slug):
	memorial = get_object_or_404(Memorial, slug=slug)
	fmt = request.GET.get("format")
	if fmt not in PRINT_FORMATS:
		fmt = "affiche"
	return render(request, "memorials/qr_print.html", {
		"memorial": memorial,
		"format": fmt,
		"formats": PRINT_FORMATS,
		"qr": mark_safe(qr_svg(memorial.public_url)),
		"short_url": memorial.public_url.split("://", 1)[-1],
	})


@staff_member_required
def qr_download(request, slug):
	memorial = get_object_or_404(Memorial, slug=slug)
	response = HttpResponse(qr_svg(memorial.public_url, standalone=True), content_type="image/svg+xml")
	response["Content-Disposition"] = f'attachment; filename="qr-{memorial.slug}.svg"'
	return response


def _client_ip(request):
	# nginx sets X-Real-IP; gunicorn only listens on a local socket so it can't be spoofed
	return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


def _rate_limited(request):
	"""At most RATE_LIMIT messages per visitor in a fixed RATE_WINDOW, counted from their first message.

	The window's end is stored with the count, so later messages don't push it back."""
	key = f"comment-rate:{_client_ip(request)}"
	now = time.time()
	count, window_end = cache.get(key) or (0, 0)
	if now >= window_end:
		count, window_end = 0, now + RATE_WINDOW
	if count >= RATE_LIMIT:
		return True
	cache.set(key, (count + 1, window_end), max(1, int(window_end - now)))
	return False
