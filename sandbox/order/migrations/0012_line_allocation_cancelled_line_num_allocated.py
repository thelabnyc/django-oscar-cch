from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("order", "0011_alter_surcharge_options_line_tax_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="line",
            name="allocation_cancelled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="line",
            name="num_allocated",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Number allocated"
            ),
        ),
    ]
