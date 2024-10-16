# Generated by Django 2.2.5 on 2019-09-27 09:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("order", "0005_auto_20170502_1553"),
    ]

    operations = [
        migrations.AlterField(
            model_name="communicationevent",
            name="date_created",
            field=models.DateTimeField(
                auto_now_add=True, db_index=True, verbose_name="Date"
            ),
        ),
        migrations.AlterField(
            model_name="paymentevent",
            name="date_created",
            field=models.DateTimeField(
                auto_now_add=True, db_index=True, verbose_name="Date created"
            ),
        ),
        migrations.AlterField(
            model_name="shippingevent",
            name="date_created",
            field=models.DateTimeField(
                auto_now_add=True, db_index=True, verbose_name="Date Created"
            ),
        ),
        migrations.CreateModel(
            name="OrderStatusChange",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "old_status",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="Old Status"
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="New Status"
                    ),
                ),
                (
                    "date_created",
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name="Date Created"
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_changes",
                        to="order.Order",
                        verbose_name="Order",
                    ),
                ),
            ],
            options={
                "verbose_name": "Order Status Change",
                "verbose_name_plural": "Order Status Changes",
                "ordering": ["-date_created"],
                "abstract": False,
            },
        ),
    ]
