from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add the amount_paid snapshot field to Purchase.

    Uses preserve_default=False so the one-off default (0) is only applied
    to existing rows during migration. The model state retains no default,
    forcing every new Purchase to set amount_paid explicitly at creation.
    """

    dependencies = [
        ("magazines", "0002_issue_price_alter_issue_is_free_purchase"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchase",
            name="amount_paid",
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    "BDT amount actually paid, snapshotted at purchase time. "
                    "Independent of future Issue.price changes — preserves audit trail."
                ),
            ),
            preserve_default=False,
        ),
    ]
