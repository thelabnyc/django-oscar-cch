from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("basket", "0005_auto_20150604_1450"),
        ("order", "0003_auto_20150113_1629"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="line",
            options={},
        ),
        migrations.AlterModelOptions(
            name="order",
            options={},
        ),
        migrations.AddField(
            model_name="line",
            name="basket_line",
            field=models.OneToOneField(
                to="basket.Line",
                null=True,
                related_name="order_line",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="is_tax_known",
            field=models.BooleanField(default=True),
        ),
    ]
