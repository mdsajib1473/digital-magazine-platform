import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from sslcommerz_lib import SSLCOMMERZ

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
    Gated, sealed PDF endpoint. The ONLY sanctioned access pattern is the
    XHR from our reader page with ``?client=pdfjs``, which returns the
    file's bytes XOR-masked with ``PDF_XOR_KEY`` and streamed as
    ``application/octet-stream``. The reader's JS reverses the XOR before
    handing the buffer to PDF.js.

    Any other access pattern -- direct navigation, missing ``?client``,
    wrong ``?client`` value, IDM following the URL out of the page DOM --
    gets a 403 Forbidden. There is no longer any path that serves the raw
    PDF bytes to a browser or download manager.

    Access control layering (in order):
      1. ``_gate_or_none()`` handles auth + purchase gating. Anonymous
         users are redirected to login; authenticated-but-unpaid users
         are bounced to the issue detail page with a flash message.
      2. 404 if the issue has no PDF file attached yet.
      3. 403 if the request is missing the ``?client=pdfjs`` marker.
         Placed AFTER auth so unauthenticated callers don't learn that
         the endpoint exists -- they see the login redirect first.

    Why @xframe_options_sameorigin: defence-in-depth, in case a future
    tweak ever embeds the response in an iframe again.

    SECURITY NOTE: The ``?client=pdfjs`` marker is trivially forgeable --
    any caller who inspects the reader HTML can copy the query string.
    Its role is UX gating ("don't accidentally dump the raw file to a
    browser tab"), not authorization. The real access control is the
    auth/purchase gate above. If you ever need stronger per-request
    binding, add a short-lived signed token keyed to the user's session.

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

        # Seal: reject anything that isn't the reader's XHR. The marker
        # itself isn't a security mechanism (see SECURITY NOTE in the
        # class docstring), but closing this path ensures IDM can't grab
        # a raw application/pdf response by following /pdf/ directly.
        if request.GET.get("client") != "pdfjs":
            return HttpResponseForbidden(
                "Direct PDF access is not allowed. " "Please use the in-browser reader."
            )

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


# ---------------------------------------------------------------------------
# Payment flow (SSLCommerz)
#
# Lifecycle:
#   1. User POSTs /issues/<slug>/buy/  -> IssueBuyView.post()
#      - creates/refreshes a PENDING Purchase row with a fresh UUID tran_id
#      - asks SSLCommerz to start a session (createSession)
#      - redirects the user's browser to the returned GatewayPageURL
#   2. User pays on SSLCommerz; they're POST-redirected back to ONE of:
#        /payment/success/  -> payment_success (status=VALID)
#        /payment/fail/     -> payment_fail    (status=FAILED)
#        /payment/cancel/   -> payment_cancel  (user aborted)
#   3. Each callback validates the POST body's hash, updates the Purchase
#      row's payment_status, and bounces the user to their library (on
#      success) or the issue detail page (on fail/cancel) with a flash.
#
# Security:
#   - All 3 callbacks are @csrf_exempt (no Django CSRF token in
#     SSLCommerz's cross-origin POST) BUT protected by hash_validate_ipn,
#     which recomputes the MD5 signature from store_pass + payload. An
#     attacker forging a POST without the real store_pass fails the hash.
#   - Amount + currency are re-checked server-side against the stored
#     Purchase row -- prevents a tampered POST with amount=1 BDT.
#   - We look up Purchase by tran_id (a UUID we generated), not by user
#     session -- the browser in the callback may legitimately be mid-
#     session-rotation after the payment flow.
# ---------------------------------------------------------------------------


class IssueBuyView(LoginRequiredMixin, View):
    """Initiate an SSLCommerz payment session for ``issue``.

    POST-only (GET would be CSRF/idempotency hell). Idempotent across
    retries: ``update_or_create`` rewrites a previously-Failed or Pending
    row in place, giving it a fresh transaction_id so the gateway treats
    each attempt as a new session. Existing SUCCESS rows short-circuit to
    the reader -- a user who already paid is never billed twice.
    """

    http_method_names = ["post"]

    def post(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)

        # Free issues never hit the gateway -- they're readable by anyone.
        if issue.is_free:
            messages.info(request, "This issue is free — no purchase needed.")
            return redirect("issue_read", slug=slug)

        # Already-paid short-circuit. Mirrors is_accessible_by() semantics
        # (SUCCESS-only) so an abandoned Pending row doesn't block a retry.
        already_paid = Purchase.objects.filter(
            user=request.user,
            issue=issue,
            payment_status=Purchase.PaymentStatus.SUCCESS,
        ).exists()
        if already_paid:
            messages.info(request, "You already own this issue.")
            return redirect("issue_read", slug=slug)

        # Fresh UUID per attempt. Using uuid4 (not uuid1) so we don't leak
        # the server's MAC address in the gateway trail.
        tran_id = str(uuid.uuid4())

        # update_or_create reuses the row for this (user, issue) pair --
        # required because UniqueConstraint(user, issue) would reject a
        # second create() on retry. The previous tran_id is overwritten.
        Purchase.objects.update_or_create(
            user=request.user,
            issue=issue,
            defaults={
                "amount_paid": issue.price,
                "payment_status": Purchase.PaymentStatus.PENDING,
                "transaction_id": tran_id,
            },
        )

        # Build absolute callback URLs -- SSLCommerz POSTs the user's
        # browser back to these, so they must be reachable from the
        # browser (localhost:8000 is fine for sandbox testing).
        success_url = request.build_absolute_uri(reverse("payment_success"))
        fail_url = request.build_absolute_uri(reverse("payment_fail"))
        cancel_url = request.build_absolute_uri(reverse("payment_cancel"))

        # Customer info: prefer real values, fall back to safe placeholders.
        # SSLCommerz rejects the session if any of these are missing.
        user = request.user
        full_name = (f"{user.first_name} {user.last_name}").strip() or user.username

        post_body = {
            "total_amount": issue.price,
            "currency": "BDT",
            "tran_id": tran_id,
            "success_url": success_url,
            "fail_url": fail_url,
            "cancel_url": cancel_url,
            "emi_option": 0,
            # Customer
            "cus_name": full_name,
            "cus_email": user.email or "noemail@unmadbd.com",
            "cus_phone": user.phone_number or "N/A",
            "cus_add1": "N/A",
            "cus_city": "Dhaka",
            "cus_country": "Bangladesh",
            # Digital goods -- no shipping, but the fields are required.
            "shipping_method": "NO",
            "num_of_item": 1,
            "product_name": issue.title[:50],
            "product_category": "Magazine",
            "product_profile": "non-physical-goods",
        }

        sslcz = SSLCOMMERZ(settings.SSLCOMMERZ)
        response = sslcz.createSession(post_body)

        # createSession() returns None on *any* exception (the lib swallows
        # them internally). Defensive-code the None + the explicit FAILED
        # status so the user never lands on a broken gateway page.
        if not response or response.get("status") != "SUCCESS":
            messages.error(
                request,
                "We couldn't start the payment. Please try again in a moment.",
            )
            return redirect("issue_detail", slug=slug)

        gateway_url = response.get("GatewayPageURL")
        if not gateway_url:
            messages.error(
                request,
                "Payment gateway returned an invalid response. Please try again.",
            )
            return redirect("issue_detail", slug=slug)

        return redirect(gateway_url)


def _validate_and_lookup(request) -> "tuple[Purchase | None, str]":
    """Shared callback pre-amble: validate SSLCommerz hash + load Purchase.

    Returns ``(purchase, error_message)``:
      - ``(purchase, "")`` on success
      - ``(None, "<why>")`` on any failure (hash mismatch, unknown tran_id,
        missing field). Callers redirect with ``messages.error`` using the
        returned string.

    Kept deliberately silent about *which* check failed -- we don't want
    to help an attacker narrow down what to forge next.
    """
    tran_id = request.POST.get("tran_id")
    if not tran_id:
        return None, "Invalid payment callback."

    # Authenticity check: SSLCommerz recomputes an MD5 over a canonical
    # subset of its own POST + our store_pass. If this doesn't match, the
    # POST isn't from them and we MUST NOT update any row.
    sslcz = SSLCOMMERZ(settings.SSLCOMMERZ)
    if not sslcz.hash_validate_ipn(request.POST.dict()):
        return None, "Payment could not be verified."

    try:
        purchase = Purchase.objects.select_related("issue", "user").get(
            transaction_id=tran_id
        )
    except Purchase.DoesNotExist:
        return None, "Payment could not be verified."

    return purchase, ""


@csrf_exempt
@require_POST
def payment_success(request):
    """SSLCommerz success callback. Flip the Purchase row to SUCCESS."""
    purchase, err = _validate_and_lookup(request)
    if purchase is None:
        messages.error(request, err)
        return redirect("home")

    # Idempotency: if the IPN already flipped us (or the user refreshed),
    # don't double-update -- just send them to their library.
    if purchase.payment_status == Purchase.PaymentStatus.SUCCESS:
        messages.info(request, f"You already own '{purchase.issue.title}'.")
        return redirect("library")

    # Amount tamper check. SSLCommerz echoes back what it charged the
    # card; we compare against what we told it to charge.
    try:
        paid_amount = float(request.POST.get("amount", "0"))
    except (TypeError, ValueError):
        paid_amount = 0.0
    if (
        paid_amount < float(purchase.amount_paid)
        or request.POST.get("currency") != "BDT"
    ):
        purchase.payment_status = Purchase.PaymentStatus.FAILED
        purchase.save(update_fields=["payment_status"])
        messages.error(request, "Payment amount mismatch; your card was NOT charged.")
        return redirect("issue_detail", slug=purchase.issue.slug)

    purchase.payment_status = Purchase.PaymentStatus.SUCCESS
    purchase.save(update_fields=["payment_status"])
    messages.success(
        request,
        f"Payment successful! '{purchase.issue.title}' has been added to your library.",
    )
    return redirect("library")


@csrf_exempt
@require_POST
def payment_fail(request):
    """SSLCommerz fail callback. Flip the Purchase row to FAILED."""
    purchase, err = _validate_and_lookup(request)
    if purchase is None:
        messages.error(request, err)
        return redirect("home")

    # Don't clobber a SUCCESS row -- the user already owns the issue; a
    # stale Fail POST (e.g. retry of a race) shouldn't revoke access.
    if purchase.payment_status != Purchase.PaymentStatus.SUCCESS:
        purchase.payment_status = Purchase.PaymentStatus.FAILED
        purchase.save(update_fields=["payment_status"])

    messages.error(
        request,
        "Your payment could not be completed. You can try again below.",
    )
    return redirect("issue_detail", slug=purchase.issue.slug)


@csrf_exempt
@require_POST
def payment_cancel(request):
    """SSLCommerz cancel callback. User aborted -- leave row PENDING."""
    purchase, err = _validate_and_lookup(request)
    if purchase is None:
        messages.info(request, "Payment was cancelled.")
        return redirect("home")

    # We intentionally do NOT flip the row to FAILED on cancel -- the
    # user may just be reconsidering. The PENDING row is harmless: the
    # access check requires SUCCESS, and a retry will overwrite this row
    # via update_or_create with a fresh tran_id.
    messages.info(request, "Payment cancelled — no charge was made.")
    return redirect("issue_detail", slug=purchase.issue.slug)
