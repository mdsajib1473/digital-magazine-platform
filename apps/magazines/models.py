from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from core.storages import private_media_storage, public_media_storage


class Category(models.Model):
    """A grouping for magazine issues (e.g. Monthly, Special, Annual)."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name


class Issue(models.Model):
    """A single magazine issue archived in the system."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=220,
        unique=True,
        allow_unicode=True,
        blank=True,
        help_text=(
            "Auto-generated from the title on save. Supports Unicode (e.g. Bengali). "
            "Leave blank unless you need a custom URL."
        ),
    )
    issue_number = models.PositiveIntegerField()
    cover_image = models.ImageField(
        upload_to="covers/",
        storage=public_media_storage,
        help_text="Cover photo. Stored in the public bucket; URL is public + cacheable.",
    )
    pdf_file = models.FileField(
        upload_to="pdfs/",
        storage=private_media_storage,
        help_text=(
            "PDF of the issue. Stored in the private bucket; .url generates a "
            "short-lived signed URL. Never expose the raw key to anonymous users."
        ),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    published_date = models.DateField()
    description = models.TextField(blank=True)
    is_free = models.BooleanField(
        default=True,
        help_text="If True, the issue is readable without a Purchase record.",
    )
    price = models.PositiveIntegerField(
        default=20,
        help_text="Price in BDT. Ignored when is_free=True.",
    )

    class Meta:
        ordering = ["-published_date", "-issue_number"]
        verbose_name = "Issue"
        verbose_name_plural = "Issues"

    def __str__(self) -> str:
        return f"{self.title} #{self.issue_number}"

    def save(self, *args, **kwargs):
        """Auto-populate slug if blank, with collision resolution.

        - slugify(allow_unicode=True) keeps Bengali characters intact.
        - If the title slugifies to an empty string (e.g. punctuation-only),
          fall back to ``issue-<number>-<YYYY-MM>`` so we always have a slug.
        - On collision, append ``-2``, ``-3`` ... until unique. The pk-aware
          .exclude ensures editing an existing issue keeps its own slug.
        """
        if not self.slug:
            base = slugify(self.title, allow_unicode=True)
            if not base:
                date_part = (
                    self.published_date.strftime("%Y-%m")
                    if self.published_date
                    else "undated"
                )
                base = f"issue-{self.issue_number}-{date_part}"

            candidate = base
            suffix = 2
            while Issue.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("issue_detail", kwargs={"slug": self.slug})

    def is_accessible_by(self, user) -> bool:
        """Whether ``user`` is allowed to read the PDF of this issue.

        Free issues are open to everyone (incl. anonymous). Paid issues
        require either staff status or a Purchase row for this user.
        """
        if self.is_free:
            return True
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return self.purchases.filter(user=user).exists()


class Purchase(models.Model):
    """A record of a single user paying for a single issue (pay-per-issue model)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    issue = models.ForeignKey(
        "Issue",
        on_delete=models.PROTECT,
        related_name="purchases",
    )
    amount_paid = models.PositiveIntegerField(
        help_text=(
            "BDT amount actually paid, snapshotted at purchase time. "
            "Independent of future Issue.price changes — preserves audit trail."
        ),
    )
    purchase_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "issue"],
                name="unique_user_issue_purchase",
            ),
        ]
        verbose_name = "Purchase"
        verbose_name_plural = "Purchases"

    def __str__(self) -> str:
        return f"{self.user} -> {self.issue}"
