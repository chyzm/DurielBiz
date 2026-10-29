from decimal import Decimal

from django.test import TestCase

from accounts.models import Business, User
from accounts.tenancy import reset_current_business_id, set_current_business_id
from products.models import BranchStock, Category, Product
from reports.models import Branch
from sales.models import Sale
from sales.services import create_sale


class ReportViewTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Report Tenant", slug="report-tenant")
        self.tenant_token = set_current_business_id(self.business.pk)
        self.admin = User.objects.create_user(username="admin_r", password="pass1234", role=User.Role.ADMIN, is_staff=True, business=self.business)
        self.branch = Branch.objects.create(name="Main", code="main")
        self.cashier = User.objects.create_user(
            username="cashier_r", password="pass1234", role=User.Role.CASHIER, branch=self.branch, business=self.business
        )
        drinks = Category.objects.create(name="Drinks")
        snacks = Category.objects.create(name="Snacks")
        self.soda = Product.objects.create(
            name="Soda", category=drinks, cost_price=Decimal("50.00"), selling_price=Decimal("100.00"), quantity=50
        )
        self.chips = Product.objects.create(
            name="Chips", category=snacks, cost_price=Decimal("80.00"), selling_price=Decimal("150.00"), quantity=50
        )
        BranchStock.objects.create(branch=self.branch, product=self.soda, quantity=50)
        BranchStock.objects.create(branch=self.branch, product=self.chips, quantity=50)

        create_sale(
            cashier=self.cashier,
            items=[{"product_id": self.soda.pk, "quantity": 3}, {"product_id": self.chips.pk, "quantity": 2}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("600.00"),
        )

    def tearDown(self):
        reset_current_business_id(self.tenant_token)
        super().tearDown()

    def test_category_report_shows_expected_totals(self):
        self.client.login(username="admin_r", password="pass1234")
        response = self.client.get("/reports/category/")
        self.assertEqual(response.status_code, 200)
        rows = {row["product__category__name"]: row for row in response.context["rows"]}
        self.assertEqual(rows["Drinks"]["quantity_sold"], 3)
        self.assertEqual(rows["Drinks"]["revenue"], Decimal("300.00"))
        self.assertEqual(rows["Snacks"]["quantity_sold"], 2)
        self.assertEqual(rows["Snacks"]["revenue"], Decimal("300.00"))

    def test_profit_by_product_report_ranks_by_profit(self):
        # Soda profit: (100-50)*3 = 150; Chips profit: (150-80)*2 = 140 -> Soda ranks first.
        self.client.login(username="admin_r", password="pass1234")
        response = self.client.get("/reports/profit/")
        self.assertEqual(response.status_code, 200)
        rows = list(response.context["rows"])
        self.assertEqual(rows[0]["product__name"], "Soda")
        self.assertEqual(rows[0]["profit"], Decimal("150.00"))
        self.assertEqual(rows[1]["product__name"], "Chips")
        self.assertEqual(rows[1]["profit"], Decimal("140.00"))

    def test_completed_sale_appears_in_sales_history_for_sale_date(self):
        sale_date = self.soda.sale_items.first().sale.created_at.date().isoformat()
        self.client.force_login(self.admin)
        response = self.client.get(
            "/sales/history/",
            {"start_date": sale_date, "end_date": sale_date, "status": "completed"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SALE-")

    def test_dashboard_chart_has_seven_valid_labels(self):
        self.client.force_login(self.admin)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        chart = response.context["sales_chart"]
        self.assertEqual(len(chart["labels"]), 7)
        self.assertEqual(len(chart["values"]), 7)
        self.assertTrue(all(isinstance(label, str) for label in chart["labels"]))
        self.assertTrue(all(isinstance(value, float) for value in chart["values"]))

    def test_category_export_csv(self):
        self.client.login(username="admin_r", password="pass1234")
        response = self.client.get("/reports/category/export/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(b"Drinks", response.content)

    def test_profit_export_pdf(self):
        self.client.login(username="admin_r", password="pass1234")
        response = self.client.get("/reports/profit/export/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_non_admin_cannot_access_reports(self):
        self.client.login(username="cashier_r", password="pass1234")
        response = self.client.get("/reports/category/")
        self.assertEqual(response.status_code, 302)
