from django.contrib import admin

from .models import Category, Issue, Purchase


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "issue_number",
        "category",
        "published_date",
        "is_free",
        "price",
    )
    list_filter = ("category", "is_free", "published_date")
    search_fields = ("title", "description")
    autocomplete_fields = ("category",)
    date_hierarchy = "published_date"
    list_per_page = 25
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("title", "issue_number", "category", "published_date"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "cover_image", "pdf_file"),
            },
        ),
        (
            "Access & Pricing",
            {
                "fields": ("is_free", "price"),
                "description": "Free issues ignore the price field. Pay-per-issue model.",
            },
        ),
    )

    class Media:
        css = {
            "all": ("css/admin_custom.css",),
        }


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "issue",
        "payment_status",
        "transaction_id",
        "amount_paid",
        "purchased_at",
    )
    list_filter = ("payment_status", "purchased_at", "issue__category")
    search_fields = (
        "user__username",
        "user__email",
        "issue__title",
        "transaction_id",
    )
    autocomplete_fields = ("user", "issue")
    date_hierarchy = "purchased_at"
    readonly_fields = ("purchased_at",)
    list_per_page = 50
    list_select_related = ("user", "issue")
