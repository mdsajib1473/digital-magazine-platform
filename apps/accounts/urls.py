"""URL configuration for the accounts app.

Includes Django's full ``django.contrib.auth.urls`` set so we get login,
logout, and password change/reset flows for free, then layers our custom
signup view + styled login form on top.
"""
from django.contrib.auth.views import LoginView
from django.urls import include, path

from .forms import StyledAuthenticationForm
from .views import SignupView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    # Override the stock login view so we can swap in the styled form, then
    # delegate the rest (logout, password_change, password_reset, ...) to the
    # default contrib.auth URLConf.
    path(
        "login/",
        LoginView.as_view(authentication_form=StyledAuthenticationForm),
        name="login",
    ),
    path("", include("django.contrib.auth.urls")),
]
