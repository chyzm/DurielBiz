from django.test import TestCase

from accounts.models import User

from .models import Business, BusinessMembership


class CloudPageSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cloud_owner",
            email="owner@example.com",
            password="pass1234",
            role=User.Role.ADMIN,
        )
        self.business = Business.objects.create(name="Cloud Test Business", owner=self.user)
        BusinessMembership.objects.create(user=self.user, business=self.business)

    def test_cloud_purchases_page_renders(self):
        self.client.login(username="cloud_owner", password="pass1234")
        response = self.client.get("/cloud/purchases/")
        self.assertEqual(response.status_code, 200)

    def test_cloud_inventory_page_renders(self):
        self.client.login(username="cloud_owner", password="pass1234")
        response = self.client.get("/cloud/inventory/")
        self.assertEqual(response.status_code, 200)
