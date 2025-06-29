from django.contrib.postgres.operations import HStoreExtension
from django.db import migrations, models
import django.contrib.postgres.fields.hstore


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        HStoreExtension(),
        migrations.CreateModel(
            name="LineItemTaxation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("country_code", models.CharField(max_length=5)),
                ("state_code", models.CharField(max_length=5)),
                (
                    "total_tax_applied",
                    models.DecimalField(max_digits=12, decimal_places=2),
                ),
                (
                    "line_item",
                    models.OneToOneField(
                        to="order.Line",
                        related_name="taxation",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LineItemTaxationDetail",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        auto_created=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("data", django.contrib.postgres.fields.hstore.HStoreField()),
                (
                    "taxation",
                    models.ForeignKey(
                        to="cch.LineItemTaxation",
                        related_name="details",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OrderTaxation",
            fields=[
                (
                    "order",
                    models.OneToOneField(
                        primary_key=True,
                        serialize=False,
                        to="order.Order",
                        related_name="taxation",
                        on_delete=models.CASCADE,
                    ),
                ),
                ("transaction_id", models.IntegerField()),
                ("transaction_status", models.IntegerField()),
                (
                    "total_tax_applied",
                    models.DecimalField(max_digits=12, decimal_places=2),
                ),
                ("messages", models.TextField(null=True)),
            ],
        ),
    ]
