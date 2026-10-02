from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Post


def post_list(request):
	posts = Post.objects.filter(is_published=True).prefetch_related("images")
	page = Paginator(posts, 9).get_page(request.GET.get("page"))
	return render(request, "news/list.html", {"page": page})


def post_detail(request, slug):
	post = get_object_or_404(Post.objects.prefetch_related("images"), slug=slug, is_published=True)
	return render(request, "news/detail.html", {"post": post})
