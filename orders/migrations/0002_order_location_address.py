# Generated by Django 5.2.1 on 2025-08-02 06:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="location_address",
            field=models.TextField(blank=True, null=True),
        ),
    ]
