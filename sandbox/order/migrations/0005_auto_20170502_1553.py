# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-05-02 15:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0004_auto_20160325_1012'),
    ]

    operations = [
        migrations.AlterField(
            model_name='line',
            name='basket_line',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_line', to='basket.Line'),
        ),
        migrations.AlterField(
            model_name='order',
            name='guest_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Guest email address'),
        ),
    ]
