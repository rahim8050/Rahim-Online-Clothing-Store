from django.db import migrations


def lowercase_payment_method(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    mapping = {
        'MPESA': 'mpesa',
        'M-PESA': 'mpesa',
        'CARD': 'card',
        'PAYPAL': 'paypal',
    }
    for upper, lower in mapping.items():
        Order.objects.filter(payment_method=upper).update(payment_method=lower)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_dest_address_text_order_dest_lat_and_more'),
    ]

    operations = [
        migrations.RunPython(lowercase_payment_method, migrations.RunPython.noop),
    ]

