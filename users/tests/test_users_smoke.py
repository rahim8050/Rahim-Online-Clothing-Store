from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from users.constants import ADMIN as ROLE_ADMIN
from users.constants import CUSTOMER as ROLE_CUSTOMER
from users.constants import DRIVER as ROLE_DRIVER
from users.constants import VENDOR as ROLE_VENDOR
from users.constants import VENDOR_STAFF as ROLE_VENDOR_STAFF


class SyncRolesTests(TestCase):
    def test_idempotent(self):
        call_command("sync_roles")
        call_command("sync_roles")
        roles = [
            ROLE_ADMIN,
            ROLE_CUSTOMER,
            ROLE_VENDOR,
            ROLE_VENDOR_STAFF,
            ROLE_DRIVER,
        ]
        for role in roles:
            self.assertEqual(Group.objects.filter(name=role).count(), 1)
