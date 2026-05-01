from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import DetailView, ListView

from .models import Issue, Purchase


class IssueListView(ListView):
    """
    Public landing page: a paginated grid of the latest issues.

    Supports a free-text search via ``?q=`` over title and description.
    Issues are ordered newest-first (by published_date, then issue_number).
    """

    model = Issue
    template_name = "magazines/issue_list.html"
    context_object_name = "issues"
    paginate_by = 12

    def get_queryset(self):
        # select_related avoids N+1 when the template renders category.name.
        qs = Issue.objects.select_related("category").order_by(
            "-published_date", "-issue_number"
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_query"] = self.request.GET.get("q", "").strip()
        return ctx


class IssueDetailView(DetailView):
    """Public issue page. Shows metadata + a context-aware CTA.

    The CTA branches into three states (computed in get_context_data):
      * has_access=True  -> Read PDF button (links to issue_read view).
      * has_access=False, user authed   -> Buy for ৳N (POST to issue_buy).
      * has_access=False, anonymous     -> Sign in to purchase (?next=).
    """

    model = Issue
    template_name = "magazines/issue_detail.html"
    context_object_name = "issue"

    def get_queryset(self):
        return Issue.objects.select_related("category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        issue: Issue = self.object
        user = self.request.user
        ctx["has_access"] = issue.is_accessible_by(user)
        ctx["needs_purchase"] = (not issue.is_free) and not ctx["has_access"]
        return ctx


def _gate_or_none(request, issue: Issue):
    """Shared access gate for the reader + raw-PDF endpoints.

    Returns ``None`` if the user is allowed through. Otherwise returns
    the appropriate HttpResponseRedirect:
      * anonymous                 -> 302 /accounts/login/?next=<current path>
      * authenticated, no access  -> 302 back to detail with a flash message

    Centralised here so the reader page and the iframe PDF endpoint can
    never drift out of sync on access logic.
    """
    if issue.is_accessible_by(request.user):
        return None
    # Anonymous FIRST: a logged-out user on a paid issue must *always* be
    # bounced to login. Keeping next=<current-path> means the 302 preserves
    # their original intent -- after logging in they return here, re-run
    # the access check, and get routed appropriately.
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    # Authenticated but lacks a Purchase: bounce to the detail page (which
    # renders the Buy CTA) with a flash so they know why they were moved.
    messages.info(
        request,
        f"You need to purchase '{issue.title}' before reading it.",
    )
    return redirect("issue_detail", slug=issue.slug)


class IssueReadView(View):
    """
    Embedded reader page.

    Renders an HTML shell containing an iframe that points at
    :class:`IssuePdfView`. The signed URL itself never appears in this
    response -- only the URL of our own gated PDF endpoint -- so
    DevTools / View-Source can't lift the link out for sharing.
    """

    def get(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)
        gated = _gate_or_none(request, issue)
        if gated is not None:
            return gated
        if not issue.pdf_file:
            raise Http404("This issue has no PDF uploaded yet.")
        return render(request, "magazines/issue_read.html", {"issue": issue})


@method_decorator(xframe_options_sameorigin, name="dispatch")
class IssuePdfView(View):
    """
    Gated PDF endpoint -- streams the file inline for the reader iframe.

    Why we stream rather than 302-to-signed-URL (the previous approach):
      1. The old 302 response got ``X-Frame-Options: DENY`` from Django's
         ``XFrameOptionsMiddleware``. Browsers enforce XFO on every
         response in a redirect chain, so the iframe refused to embed
         the PDF at all -- result: blank iframe.
      2. Even if the iframe could follow, ``django.views.static.serve``
         (DEBUG media handler) doesn't set ``Content-Disposition``, which
         Chrome/Edge treat as ambiguous and often downloads instead of
         rendering inline.

    ``FileResponse(..., as_attachment=False, content_type="application/pdf")``
    fixes both: it sets ``Content-Disposition: inline; filename="..."``,
    and the ``@xframe_options_sameorigin`` decorator overrides the DENY
    header so our own same-origin reader iframe can load it.

    PRODUCTION NOTE: When PrivateMediaStorage is backed by Supabase/S3,
    this view still works (it streams through Django) but is bandwidth-
    expensive -- every read proxies the file through our server. The
    optimisation path is to 302 to a signed URL with query parameter
    ``response-content-disposition=inline`` so the CDN sets it. Document
    that swap when wiring real Supabase.
    """

    def get(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)
        gated = _gate_or_none(request, issue)
        if gated is not None:
            return gated
        if not issue.pdf_file:
            raise Http404("This issue has no PDF uploaded yet.")
        return FileResponse(
            issue.pdf_file.open("rb"),
            as_attachment=False,
            filename=f"{issue.slug}.pdf",
            content_type="application/pdf",
        )


class IssueBuyView(LoginRequiredMixin, View):
    """
    Placeholder purchase endpoint until a real payment gateway is wired.

    POST-only (creating purchases via GET would be CSRF/idempotency hell).
    Idempotent thanks to UniqueConstraint(user, issue) -> get_or_create
    silently no-ops on a duplicate.
    """

    http_method_names = ["post"]

    def post(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)

        if issue.is_free:
            messages.info(request, "This issue is free — no purchase needed.")
            return redirect("issue_read", slug=slug)

        purchase, created = Purchase.objects.get_or_create(
            user=request.user,
            issue=issue,
            defaults={"amount_paid": issue.price},
        )
        if created:
            messages.success(
                request,
                f"Purchase confirmed! Enjoy '{issue.title}'.",
            )
        else:
            messages.info(request, "You already own this issue.")

        return redirect("issue_read", slug=slug)
