from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0007_order_payment_intent_id_order_payment_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('method', models.CharField(choices=[('card', 'Card'), ('mpesa', 'M-Pesa'), ('paypal', 'PayPal')], max_length=10)),
                ('gateway', models.CharField(choices=[('paystack', 'Paystack'), ('daraja', 'Daraja'), ('paypal', 'PayPal')], max_length=10)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('reference', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
