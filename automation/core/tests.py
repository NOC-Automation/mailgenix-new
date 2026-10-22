import json

from django.test import TestCase
from django.urls import reverse

from .models import AR, ARGroup, Customers, FloorLevel, Rack, SiteLocation, User


class MailGenixDynamicAuthorizedPersonTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-test", password="test-pass-123", role="admin",
            is_staff=True, is_superuser=True,
        )
        self.user = User.objects.create_user(
            username="user-test", password="test-pass-123", role="user",
        )
        self.site = SiteLocation.objects.create(name="JKT3")
        self.floor = FloorLevel.objects.create(name="Level 1", site_location=self.site)
        self.rack = Rack.objects.create(name_racks="RACK-A01", floor_level=self.floor)
        self.customer = Customers.objects.create(name_customer="PT Dynamic Test", created_by=self.admin)
        self.customer.racks.add(self.rack)
        self.group = ARGroup.objects.create(customer=self.customer, rack=self.rack, validity_AR="Valid")

        for i in range(1, 6):
            AR.objects.create(
                customer=self.customer,
                ar_group=self.group,
                authorized_name=f"Person {i}",
                email_address=f"person{i}@example.com",
                mobile_phone=f"0812000000{i}",
            )

    def test_prefill_returns_all_authorized_persons(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("api_tenants_by_customer", args=[self.customer.id]),
            {"group_id": self.group.id, "rack_id": self.rack.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["ars"]), 5)

    def test_update_uses_ar_ids_not_array_position(self):
        self.client.force_login(self.admin)
        ars = list(AR.objects.filter(customer=self.customer, ar_group=self.group).order_by("id"))
        payload = {
            "customer_name": self.customer.name_customer,
            "customer_site": self.site.name,
            "floor_level": self.floor.id,
            "floor_name": self.floor.name,
            "rack_id": self.rack.id,
            "rack_name": self.rack.name_racks,
            "old_rack_id": self.rack.id,
            "group_id": self.group.id,
            "validity": "Valid",
            "date": None,
            # Reverse the array and edit one person. IDs must keep identity stable.
            "ars": [
                {
                    "id": ar.id,
                    "authorized_name": ("Renamed Person" if ar.id == ars[0].id else ar.authorized_name),
                    "email": ar.email_address,
                    "phone": ar.mobile_phone,
                }
                for ar in reversed(ars)
            ],
        }
        response = self.client.put(
            reverse("api_tenants_by_customer", args=[self.customer.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        ars[0].refresh_from_db()
        self.assertEqual(ars[0].authorized_name, "Renamed Person")
        self.assertEqual(AR.objects.filter(customer=self.customer).count(), 5)

    def test_update_requires_group_id(self):
        self.client.force_login(self.admin)
        payload = {
            "customer_name": self.customer.name_customer,
            "customer_site": self.site.name,
            "floor_level": self.floor.id,
            "floor_name": self.floor.name,
            "rack_id": self.rack.id,
            "rack_name": self.rack.name_racks,
            "old_rack_id": self.rack.id,
            "ars": [{
                "id": AR.objects.filter(customer=self.customer).first().id,
                "authorized_name": "Person",
                "email": "person1@example.com",
                "phone": "0812",
            }],
        }
        response = self.client.put(
            reverse("api_tenants_by_customer", args=[self.customer.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


    def test_recipient_resolver_uses_location_and_fields(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("api_mailing_recipients"),
            {"site_id": self.site.id, "floor_id": self.floor.id, "customer_id": self.customer.id},
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["mode"], "specific-customer")
        self.assertEqual(len(data["to"]), 5)
        self.assertEqual(data["bcc"], [])

    def test_non_admin_cannot_use_user_management_api(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("api_users_list_create"))
        self.assertEqual(response.status_code, 403)
