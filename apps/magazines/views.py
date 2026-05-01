import base64

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
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
    Gated PDF endpoint -- two response modes selected by ?client query:

      * ?client=pdfjs (XHR from our reader page): the PDF bytes are Base64-
        encoded and wrapped inside a JSON object: ``{"pdf_data": "..."}``.
        IDM and similar download managers do heuristic body sniffing -- a
        plain octet-stream still gets intercepted because they recognise the
        ``%PDF-`` magic bytes at offset 0. By wrapping the bytes inside a
        JSON string with Base64 encoding, the literal ``%PDF-`` substring
        never appears in the response body and IDM ignores it as plain JSON.

      * No query (direct navigation, e.g. "Open raw PDF in a new tab"
        escape hatch): real ``application/pdf`` inline response so the
        browser's native viewer can render it normally.

    TRADE-OFFS for the JSON mode (acknowledged):
      - +33% bandwidth (Base64 inflation: 3 bytes encoded as 4 chars).
      - No HTTP Range / streaming: PDF.js can't render page 1 until the
        entire file has downloaded and Base64-decoded.
      - Whole PDF held in Django RAM per concurrent request: ~1.33x
        filesize. With 10 concurrent reads of a 50MB PDF that's ~670MB.
      - ``onProgress`` granularity drops to download-only (no parse phase).
    Re-evaluate this approach if you ever serve >100MB PDFs or need
    first-page latency under ~10s on slow connections. The lower-cost
    alternative is an XOR byte-mask on the FileResponse stream, which
    preserves Range requests at zero bandwidth overhead.

    Why @xframe_options_sameorigin: defence-in-depth, in case a future
    tweak ever embeds the response in an iframe again.

    PRODUCTION NOTE: With Supabase/S3-backed storage, the JSON path means
    Django pulls the full file from object storage on every read instead
    of 302-redirecting to a signed URL. Bandwidth doubles (storage->Django
    + Django->client). Plan to revisit this when the magazine catalogue
    or concurrent reader count grows.
    """

    def get(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)
        gated = _gate_or_none(request, issue)
        if gated is not None:
            return gated
        if not issue.pdf_file:
            raise Http404("This issue has no PDF uploaded yet.")

        if request.GET.get("client") == "pdfjs":
            # IDM-evasion mode v2: full Base64-in-JSON encoding so the
            # ``%PDF-`` magic bytes never appear in the response body.
            with issue.pdf_file.open("rb") as fh:
                pdf_bytes = fh.read()
            encoded = base64.b64encode(pdf_bytes).decode("ascii")
            return JsonResponse({"pdf_data": encoded})

        # Direct-navigation mode: real PDF labels for the native viewer.
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
