from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_orderitem_warehouse'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='delivery_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('dispatched', 'Dispatched'), ('in_transit', 'In transit'), ('delivered', 'Delivered')],
                default='pending',
                max_length=20,
            ),
        ),
    ]
