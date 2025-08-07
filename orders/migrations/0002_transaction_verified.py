from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="verified",
            field=models.BooleanField(default=False),
        ),
    ]
