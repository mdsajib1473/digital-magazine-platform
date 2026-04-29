from django.conf import settings
from django.db import models

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
