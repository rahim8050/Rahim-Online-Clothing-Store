from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import ProgrammingError
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from core.siteutils import absolute_url, current_domain


@override_settings(SITE_ID=1)
class AuthAndSitesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username='rahim',
            email='rahim@example.com',
            password='StrongPass!123',
        )
        try:
            self.login_url = reverse('login')
        except NoReverseMatch:
            self.login_url = '/login/'

    def test_login_success(self):
        response = self.client.post(
            self.login_url,
            {'username': 'rahim', 'password': 'StrongPass!123'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.headers.get('Location', ''))
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_login_invalid_password(self):
        response = self.client.post(
            self.login_url,
            {'username': 'rahim', 'password': 'Nope'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.session.get('_auth_user_id'))
        list(get_messages(response.wsgi_request))

    def test_inactive_user_denied(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        response = self.client.post(
            self.login_url,
            {'username': 'rahim', 'password': 'StrongPass!123'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.session.get('_auth_user_id'))

    def test_absolute_url_uses_request_when_available(self):
        resp = self.client.get(self.login_url)
        built = absolute_url('/activate/x/y/', request=resp.wsgi_request)
        self.assertTrue(built.startswith('http'))
        self.assertIn('activate', built)

    @patch('django.contrib.sites.models.Site.objects.get_current', side_effect=ProgrammingError('missing table'))
    def test_current_domain_fallback_without_sites_table(self, _mock):
        dom = current_domain(None)
        self.assertTrue(isinstance(dom, str) and dom)
