from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
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


class IssueReadView(View):
    """
    Gated download endpoint.

    Server-side access check, then mints a fresh signed URL via
    ``issue.pdf_file.url`` (PrivateMediaStorage) and 302s the user
    straight to it. The signed URL is *never* embedded in any HTML —
    that prevents leakage to anonymous viewers via View-Source.
    """

    def get(self, request, slug: str):
        issue = get_object_or_404(Issue, slug=slug)

        if not issue.is_accessible_by(request.user):
            if request.user.is_authenticated:
                # Logged in but no purchase -> bounce to detail (Buy CTA).
                messages.info(
                    request,
                    f"You need to purchase '{issue.title}' before reading it.",
                )
                return redirect("issue_detail", slug=slug)
            # Anonymous -> /accounts/login/?next=/issues/<slug>/read/
            return redirect_to_login(request.get_full_path())

        if not issue.pdf_file:
            raise Http404("This issue has no PDF uploaded yet.")

        # .url calls into PrivateMediaStorage and returns a signed URL
        # (or /media/pdfs/... in local FS mode).
        return redirect(issue.pdf_file.url)


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
