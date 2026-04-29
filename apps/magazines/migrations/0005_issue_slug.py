"""
Add the unicode-aware ``slug`` field to Issue.

Done in three operations within one migration so we never have a moment
where existing rows violate ``unique=True``:

  1. AddField with blank=True, default="" and NO unique constraint.
  2. RunPython populates a slug for every existing row, mirroring the
     auto-generation logic in Issue.save().
  3. AlterField promotes the column to unique=True (matching final model state).

Reverse: just drop the column.
"""
from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Issue = apps.get_model("magazines", "Issue")

    for issue in Issue.objects.all().order_by("pk"):
        base = slugify(issue.title, allow_unicode=True)
        if not base:
            date_part = (
                issue.published_date.strftime("%Y-%m")
                if issue.published_date
                else "undated"
            )
            base = f"issue-{issue.issue_number}-{date_part}"

        candidate = base
        suffix = 2
        while (
            Issue.objects.filter(slug=candidate)
            .exclude(pk=issue.pk)
            .exists()
        ):
            candidate = f"{base}-{suffix}"
            suffix += 1

        issue.slug = candidate
        issue.save(update_fields=["slug"])


def reverse_noop(apps, schema_editor):
    """Reversing AlterField/AddField drops the column; nothing else to do."""


class Migration(migrations.Migration):

    dependencies = [
        ("magazines", "0004_alter_issue_cover_image_alter_issue_pdf_file"),
    ]

    operations = [
        # 1. Add the column without unique= so existing rows can default to "".
        migrations.AddField(
            model_name="issue",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                default="",
                max_length=220,
            ),
            preserve_default=False,
        ),
        # 2. Backfill slugs for every existing row.
        migrations.RunPython(populate_slugs, reverse_noop),
        # 3. Now that every row has a unique slug, lock the constraint in.
        migrations.AlterField(
            model_name="issue",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                help_text=(
                    "Auto-generated from the title on save. Supports Unicode "
                    "(e.g. Bengali). Leave blank unless you need a custom URL."
                ),
                max_length=220,
                unique=True,
            ),
        ),
    ]
