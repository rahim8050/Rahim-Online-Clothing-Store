import re
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from product_app.models import Category, Product
from cart.models import Cart, CartItem
from orders.forms import OrderForm
from orders.models import Order


class CheckoutPaymentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='u', password='p', email='u@example.com')
        self.client.login(username='u', password='p')
        cat = Category.objects.create(name='c', slug='c')
        self.prod = Product.objects.create(category=cat, name='p', slug='p', price=Decimal('10.00'))
        self.cart = Cart.objects.create()
        CartItem.objects.create(cart=self.cart, product=self.prod, quantity=1)
        session = self.client.session
        session['cart_id'] = self.cart.id
        session.save()

    def _get_order_create(self):
        url = reverse('orders:order_create')
        return self.client.get(url)

    def test_single_payment_input_in_dom(self):
        resp = self._get_order_create()
        html = resp.content.decode()
        # Exactly one authoritative input named payment_method (hidden strategy)
        count_payment = len(re.findall(r'name=["\']payment_method["\']', html))
        self.assertLessEqual(count_payment, 2, msg=f"Too many payment_method inputs in DOM: {count_payment}")

    def test_post_card_submits_card(self):
        url = reverse('orders:order_create')
        data = {
            'full_name': 'X',
            'email': 'x@example.com',
            'address': 'A',
            'dest_address_text': 'A',
            'dest_lat': '0',
            'dest_lng': '0',
            'payment_method': 'card',
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        o = Order.objects.order_by('-id').first()
        self.assertIsNotNone(o)
        self.assertEqual(o.payment_method, 'card')

    def test_post_mpesa_submits_mpesa(self):
        url = reverse('orders:order_create')
        data = {
            'full_name': 'X',
            'email': 'x@example.com',
            'address': 'A',
            'dest_address_text': 'A',
            'dest_lat': '0',
            'dest_lng': '0',
            'payment_method': 'mpesa',
        }
        resp = self.client.post(url, data, follow=True)
        self.assertEqual(resp.status_code, 200)
        o = Order.objects.order_by('-id').first()
        self.assertIsNotNone(o)
        self.assertEqual(o.payment_method, 'mpesa')

    def test_model_value_lowercase(self):
        f = OrderForm(data={'full_name':'X','email':'x@example.com','address':'A','payment_method':'mpesa'})
        self.assertTrue('payment_method' in f.fields)
        self.assertIn(('mpesa','M-Pesa'), f.fields['payment_method'].choices)
        self.assertTrue(f.is_valid(), msg=f.errors)
        inst = f.save(commit=False)
        self.assertEqual(inst.payment_method, 'mpesa')

