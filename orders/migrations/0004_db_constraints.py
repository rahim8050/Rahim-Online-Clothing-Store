from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0003_alter_orderitem_delivery_status_and_more'),
        ('product_app', '0003_remove_warehouse_wh_lat_range_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='order',
            constraint=models.CheckConstraint(
                check=(
                    (Q(latitude__gte=-90) & Q(latitude__lte=90) &
                     Q(longitude__gte=-180) & Q(longitude__lte=180)) |
                    (Q(latitude__isnull=True) & Q(longitude__isnull=True))
                ),
                name='order_lat_lng_range_or_null',
            ),
        ),
        migrations.AddConstraint(
            model_name='orderitem',
            constraint=models.CheckConstraint(
                check=Q(delivery_status='created') | Q(warehouse__isnull=False),
                name='item_requires_warehouse_when_moving',
            ),
        ),
        migrations.RunSQL(
            sql=(
                'ALTER TABLE product_app_warehouse '
                'ADD CONSTRAINT warehouse_lat_lng_range '
                'CHECK (latitude BETWEEN -90 AND 90 AND '
                'longitude BETWEEN -180 AND 180)'
            ),
            reverse_sql=(
                'ALTER TABLE product_app_warehouse '
                'DROP CONSTRAINT warehouse_lat_lng_range'
            ),
        ),
    ]
