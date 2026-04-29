"""URL configuration for the magazines app."""
from django.urls import path

from .views import IssueListView

urlpatterns = [
    # Root of the magazines app == site landing page (named 'home' so settings'
    # LOGIN_REDIRECT_URL / LOGOUT_REDIRECT_URL keep resolving).
    path("", IssueListView.as_view(), name="home"),
]
