from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .emails import notify_moderators, send_private_comment
from .forms import CommentForm
from .models import Comment, Memorial

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
	form = CommentForm(request.POST or None, memorial=memorial)

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
			if comment.is_private:
				comment.status = Comment.Status.PENDING
				comment.save()
				comment.status = Comment.Status.SENT if send_private_comment(comment) else Comment.Status.FAILED
				comment.save(update_fields=["status"])
				messages.success(request, "Merci, votre message a été transmis à la famille.")
			else:
				comment.status = Comment.Status.PENDING
				comment.save()
				notify_moderators(comment)
				messages.success(request, "Merci, votre message sera publié sur cette page après validation.")
			return redirect(memorial.get_absolute_url() + "#messages")

	public_comments = memorial.comments.filter(
		visibility=Comment.Visibility.PUBLIC, status=Comment.Status.APPROVED
	).order_by("created_at")
	return render(request, "memorials/detail.html", {
		"memorial": memorial,
		"comments": public_comments,
		"form": form,
	})


def _client_ip(request):
	# nginx sets X-Real-IP; gunicorn only listens on a local socket so it can't be spoofed
	return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")


def _rate_limited(request):
	key = f"comment-rate:{_client_ip(request)}"
	count = cache.get(key, 0)
	if count >= RATE_LIMIT:
		return True
	cache.set(key, count + 1, RATE_WINDOW)
	return False
