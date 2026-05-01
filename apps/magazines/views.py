from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import DetailView, ListView

from .models import Issue, Purchase


# ---------------------------------------------------------------------------
# IDM-evasion XOR mask
#
# IDM (Internet Download Manager) and similar tools intercept HTTP responses
# whose bodies start with the ``%PDF-`` magic bytes -- they do this regardless
# of the Content-Type header. By XOR-ing every byte with a fixed key before
# streaming, we ensure the literal ``%PDF-`` byte sequence never appears in
# the response body. The client reverses the mask in JS before handing the
# bytes to PDF.js.
#
# Trade-offs vs. Base64-in-JSON (which we used previously):
#   - Bandwidth: 1.0x file size (Base64 was 1.33x).
#   - Server RAM: streaming chunks (~64 KB) per request (Base64 held the
#     entire file in memory while JsonResponse serialised it).
#   - Time-to-first-page: same as Base64 (PDF.js still needs the whole
#     buffer for ``data:`` mode), but the network phase is faster.
#   - Range requests: not used by client (PDF.js ``data:`` mode), but the
#     server side could support them if needed -- XOR is a per-byte op,
#     so any byte range can be masked independently.
#
# SECURITY NOTE: This is obfuscation, not encryption. Anyone with DevTools
# can read the unmasked bytes from PDF.js's parsed Uint8Array, just like
# they can with any client-rendered PDF reader. The goal here is purely to
# evade IDM's heuristic body sniffing. Real anti-piracy requires per-user
# watermarking baked into the PDF before streaming.
#
# The key value MUST match ``PDF_XOR_KEY`` in the reader template's JS
# (apps/magazines/templates/magazines/issue_read.html). If you change one,
# change both.
PDF_XOR_KEY = 0xAA
# Lookup table for fast XOR via ``bytes.translate()``: at our 64 KB chunk
# size this is ~1 GB/s in CPython vs. ~50 MB/s for a per-byte generator
# expression. Built once at import time.
_PDF_XOR_TABLE = bytes(b ^ PDF_XOR_KEY for b in range(256))


def _xor_pdf_stream(file_obj, chunk_size=64 * 1024):
    """
    Yield the file's bytes XOR-masked with ``PDF_XOR_KEY`` in fixed-size
    chunks. Closes ``file_obj`` on exhaustion or exception so we don't leak
    file descriptors when many readers connect concurrently.
    """
    try:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            yield chunk.translate(_PDF_XOR_TABLE)
    finally:
        file_obj.close()


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
    Gated PDF endpoint -- two response modes selected by ``?client``:

      * ?client=pdfjs (XHR from our reader page): bytes are XOR-masked with
        ``PDF_XOR_KEY`` and streamed as ``application/octet-stream``. The
        ``%PDF-`` magic bytes never appear in the wire bytes, so IDM's
        heuristic body-sniffing skips the response. The reader's JS
        reverses the XOR before passing the buffer to PDF.js. Streamed in
        64 KB chunks so the server never holds the whole file in RAM,
        regardless of concurrent reader count.

      * No query: real ``application/pdf`` inline response. This path now
        only exists for completeness / testing / admin debugging -- the
        reader template no longer exposes a link to it. Direct URL access
        will still hit IDM, which is precisely why we removed the link.

    Why @xframe_options_sameorigin: defence-in-depth, in case a future
    tweak ever embeds the response in an iframe again.

    PRODUCTION NOTE: With Supabase/S3-backed storage, this view streams
    bytes through Django on every read. The optimisation path is to 302
    to a signed URL with appropriate headers; the IDM-evasion mode would
    need an edge-side XOR transform (Cloudflare Worker, etc.) to preserve
    the magic-byte hiding. Plan that migration when reader concurrency
    starts saturating the Django process.
    """

    def get(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)
        gated = _gate_or_none(request, issue)
        if gated is not None:
            return gated
        if not issue.pdf_file:
            raise Http404("This issue has no PDF uploaded yet.")

        if request.GET.get("client") == "pdfjs":
            # IDM-evasion mode: streaming XOR-masked bytes. Generic labels
            # (octet-stream + stream.dat) on top of the masked body so IDM
            # has nothing to sniff -- not the headers, not the magic bytes.
            resp = StreamingHttpResponse(
                _xor_pdf_stream(issue.pdf_file.open("rb")),
                content_type="application/octet-stream",
            )
            resp["Content-Disposition"] = 'inline; filename="stream.dat"'
            # Set Content-Length so the JS streaming reader can show a real
            # progress percentage. XOR is byte-preserving, so the masked
            # output is exactly the same size as the source.
            resp["Content-Length"] = str(issue.pdf_file.size)
            return resp

        # Direct-navigation mode: real PDF labels (now only used for
        # admin/testing -- the reader UI no longer links to this).
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
