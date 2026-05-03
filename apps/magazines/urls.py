"""URL configuration for the magazines app."""

from django.urls import path

# Importing this module registers the <uslug:> path converter that lets
# Bengali (and other non-ASCII) slugs match in URL patterns.
from . import converters  # noqa: F401  (side-effect import)
from .views import (
    IssueBuyView,
    IssueDetailView,
    IssueListView,
    IssuePdfView,
    IssueReadView,
    payment_cancel,
    payment_fail,
    payment_success,
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
        "issues/<uslug:slug>/pdf/",
        IssuePdfView.as_view(),
        name="issue_pdf",
    ),
    path(
        "issues/<uslug:slug>/buy/",
        IssueBuyView.as_view(),
        name="issue_buy",
    ),
    # SSLCommerz callbacks. These receive POST from the gateway; they must
    # NOT be slug-scoped because the callback looks up the Purchase row by
    # transaction_id (which SSLCommerz echoes back in the POST body).
    path("payment/success/", payment_success, name="payment_success"),
    path("payment/fail/", payment_fail, name="payment_fail"),
    path("payment/cancel/", payment_cancel, name="payment_cancel"),
]
