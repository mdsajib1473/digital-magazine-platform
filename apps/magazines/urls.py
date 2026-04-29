"""URL configuration for the magazines app."""

from django.urls import path

# Importing this module registers the <uslug:> path converter that lets
# Bengali (and other non-ASCII) slugs match in URL patterns.
from . import converters  # noqa: F401  (side-effect import)
from .views import (
    IssueBuyView,
    IssueDetailView,
    IssueListView,
    IssueReadView,
)

urlpatterns = [
    # Root of the magazines app == site landing page (named 'home' so settings'
    # LOGIN_REDIRECT_URL / LOGOUT_REDIRECT_URL keep resolving).
    path("", IssueListView.as_view(), name="home"),
    path(
        "issues/<uslug:slug>/",
        IssueDetailView.as_view(),
        name="issue_detail",
    ),
    path(
        "issues/<uslug:slug>/read/",
        IssueReadView.as_view(),
        name="issue_read",
    ),
    path(
        "issues/<uslug:slug>/buy/",
        IssueBuyView.as_view(),
        name="issue_buy",
    ),
]
