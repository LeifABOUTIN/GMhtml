"""Only Google accounts listed in ADMIN_EMAILS may sign in; nobody can sign up otherwise."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect


def _email(sociallogin):
	return (sociallogin.user.email or sociallogin.account.extra_data.get("email") or "").lower()


class NoSignupAccountAdapter(DefaultAccountAdapter):
	def is_open_for_signup(self, request):
		return False


class AdminOnlySocialAccountAdapter(DefaultSocialAccountAdapter):
	def is_open_for_signup(self, request, sociallogin):
		return _email(sociallogin) in settings.ADMIN_EMAILS

	def pre_social_login(self, request, sociallogin):
		email = _email(sociallogin)
		verified = sociallogin.account.extra_data.get("email_verified", False)
		if email not in settings.ADMIN_EMAILS or not verified:
			messages.error(request, f"Le compte {email or 'Google'} n’est pas autorisé à administrer le site.")
			raise ImmediateHttpResponse(redirect("admin:login"))
		# keep admin rights in sync with the allow-list on every login
		user = sociallogin.user
		user.is_staff = user.is_superuser = True
		if sociallogin.is_existing:
			user.save(update_fields=["is_staff", "is_superuser"])

	def populate_user(self, request, sociallogin, data):
		user = super().populate_user(request, sociallogin, data)
		user.is_staff = user.is_superuser = True
		return user
