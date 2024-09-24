# Generated by Django 4.2.11 on 2024-06-14 15:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("order", "0013_set_num_allocated_to_quantity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="line",
            name="num_allocated",
            field=models.PositiveIntegerField(verbose_name="Number allocated"),
        ),
    ]
