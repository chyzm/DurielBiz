from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from inventory.models import InventoryLog
from products.models import BranchStock, Category, Product
from reports.models import Branch, BusinessSettings

from .models import Customer, Sale
from .services import compute_sale_preview, create_sale, void_sale


class VoidSaleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", password="pass1234", role=User.Role.ADMIN, is_staff=True)
        self.branch = Branch.objects.create(name="Main", code="main")
        self.cashier = User.objects.create_user(
            username="cashier1", password="pass1234", role=User.Role.CASHIER, branch=self.branch
        )
        category = Category.objects.create(name="Snacks")
        self.product = Product.objects.create(
            name="Biscuit", category=category, cost_price=Decimal("100.00"), selling_price=Decimal("200.00"), quantity=50
        )
        BranchStock.objects.create(branch=self.branch, product=self.product, quantity=50)

        self.sale = create_sale(
            cashier=self.cashier,
            items=[{"product_id": self.product.pk, "quantity": 5}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("1000.00"),
            customer_name="Jane",
            customer_phone="08011112222",
        )

    def test_create_sale_decrements_stock_and_awards_points(self):
        self.product.refresh_from_db()
        stock = BranchStock.objects.get(branch=self.branch, product=self.product)
        self.assertEqual(stock.quantity, 45)
        self.assertEqual(self.product.quantity, 45)
        customer = Customer.objects.get(phone="08011112222")
        self.assertEqual(customer.loyalty_points, self.sale.loyalty_points_awarded)
        self.assertEqual(customer.total_spent, self.sale.total)

    def test_void_sale_restores_stock_and_reverses_loyalty(self):
        customer = Customer.objects.get(phone="08011112222")
        points_awarded = self.sale.loyalty_points_awarded
        sale_total = self.sale.total

        void_sale(sale=self.sale, voided_by=self.admin, reason="Customer returned item")

        self.product.refresh_from_db()
        stock = BranchStock.objects.get(branch=self.branch, product=self.product)
        self.assertEqual(stock.quantity, 50)
        self.assertEqual(self.product.quantity, 50)

        customer.refresh_from_db()
        self.assertEqual(customer.loyalty_points, 0)
        self.assertEqual(customer.total_spent, Decimal("0.00"))

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status, Sale.Status.VOIDED)
        self.assertEqual(self.sale.voided_by, self.admin)
        self.assertEqual(self.sale.void_reason, "Customer returned item")
        self.assertIsNotNone(self.sale.voided_at)

        refund_logs = InventoryLog.objects.filter(source=InventoryLog.Source.REFUND, reference=self.sale.receipt_number)
        self.assertEqual(refund_logs.count(), 1)
        self.assertEqual(refund_logs.first().quantity, 5)
        self.assertGreater(points_awarded + 1, 0)  # sanity: points_awarded was computed pre-void
        self.assertGreater(sale_total, 0)

    def test_void_requires_reason(self):
        with self.assertRaises(ValidationError):
            void_sale(sale=self.sale, voided_by=self.admin, reason="")

    def test_cannot_void_already_voided_sale(self):
        void_sale(sale=self.sale, voided_by=self.admin, reason="First void")
        with self.assertRaises(ValidationError):
            void_sale(sale=self.sale, voided_by=self.admin, reason="Second attempt")

    def test_void_view_requires_admin(self):
        self.client.login(username="cashier1", password="pass1234")
        response = self.client.get(f"/sales/receipt/{self.sale.pk}/void/")
        self.assertEqual(response.status_code, 302)

    def test_void_view_end_to_end(self):
        self.client.login(username="admin1", password="pass1234")
        response = self.client.post(f"/sales/receipt/{self.sale.pk}/void/", {"reason": "Wrong item rung up"})
        self.assertEqual(response.status_code, 302)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status, Sale.Status.VOIDED)

    def test_void_view_rejects_missing_reason(self):
        self.client.login(username="admin1", password="pass1234")
        response = self.client.post(f"/sales/receipt/{self.sale.pk}/void/", {"reason": ""})
        self.assertEqual(response.status_code, 200)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status, Sale.Status.COMPLETED)


class ReceiptAccessTests(TestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(name="Branch A", code="branch-a")
        self.branch_b = Branch.objects.create(name="Branch B", code="branch-b")
        self.cashier_a = User.objects.create_user(
            username="cashierA", password="pass1234", role=User.Role.CASHIER, branch=self.branch_a
        )
        self.cashier_b = User.objects.create_user(
            username="cashierB", password="pass1234", role=User.Role.CASHIER, branch=self.branch_b
        )
        category = Category.objects.create(name="Drinks")
        product = Product.objects.create(
            name="Soda", category=category, cost_price=Decimal("50.00"), selling_price=Decimal("100.00"), quantity=20
        )
        BranchStock.objects.create(branch=self.branch_a, product=product, quantity=20)
        self.sale_a = create_sale(
            cashier=self.cashier_a,
            items=[{"product_id": product.pk, "quantity": 1}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("100.00"),
        )

    def test_cashier_can_view_own_branch_receipt(self):
        self.client.login(username="cashierA", password="pass1234")
        response = self.client.get(f"/sales/receipt/{self.sale_a.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_view_other_branch_receipt(self):
        self.client.login(username="cashierB", password="pass1234")
        response = self.client.get(f"/sales/receipt/{self.sale_a.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_receipt_search_scoped_to_branch(self):
        self.client.login(username="cashierB", password="pass1234")
        response = self.client.get("/sales/receipts/search/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.sale_a.receipt_number)


class VatCalculationTests(TestCase):
    def setUp(self):
        self.cashier = User.objects.create_user(username="vat_cashier", password="pass1234", role=User.Role.CASHIER)
        category = Category.objects.create(name="Vat Category")
        self.product = Product.objects.create(
            name="Taxable Item", category=category, cost_price=Decimal("50.00"), selling_price=Decimal("100.00"), quantity=50
        )

    def test_vat_applied_when_enabled(self):
        settings_obj = BusinessSettings.get_solo()
        settings_obj.vat_enabled = True
        settings_obj.vat_rate_percent = Decimal("7.50")
        settings_obj.save()

        sale = create_sale(
            cashier=self.cashier,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("215.00"),
        )
        # subtotal 200.00, no discount, VAT 7.5% = 15.00, total = 215.00
        self.assertEqual(sale.tax, Decimal("15.00"))
        self.assertEqual(sale.total, Decimal("215.00"))

    def test_vat_applied_after_discount(self):
        settings_obj = BusinessSettings.get_solo()
        settings_obj.vat_enabled = True
        settings_obj.vat_rate_percent = Decimal("10.00")
        settings_obj.save()

        sale = create_sale(
            cashier=self.cashier,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("198.00"),
            discount=Decimal("20.00"),
        )
        # subtotal 200 - discount 20 = 180 taxable; VAT 10% = 18.00; total = 200 - 20 + 18 = 198.00
        self.assertEqual(sale.tax, Decimal("18.00"))
        self.assertEqual(sale.total, Decimal("198.00"))

    def test_no_vat_when_disabled(self):
        settings_obj = BusinessSettings.get_solo()
        settings_obj.vat_enabled = False
        settings_obj.save()

        sale = create_sale(
            cashier=self.cashier,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("100.00"),
        )
        self.assertEqual(sale.tax, Decimal("0.00"))


class CheckoutPreviewTests(TestCase):
    def setUp(self):
        branch = Branch.objects.create(name="Preview Branch", code="preview-branch")
        self.cashier = User.objects.create_user(
            username="preview_cashier", password="pass1234", role=User.Role.CASHIER, branch=branch
        )
        category = Category.objects.create(name="Preview Category")
        self.product = Product.objects.create(
            name="Preview Item", category=category, cost_price=Decimal("50.00"), selling_price=Decimal("100.00"), quantity=10
        )
        BranchStock.objects.create(branch=branch, product=self.product, quantity=10)

    def test_preview_does_not_write_to_database(self):
        preview = compute_sale_preview(
            cashier=self.cashier,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            payment_method=Sale.PaymentMethod.CASH,
            paid_amount=Decimal("200.00"),
        )
        self.assertEqual(preview.receipt_number, "PREVIEW")
        self.assertEqual(preview.total, Decimal("200.00"))
        self.assertEqual(Sale.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)  # stock untouched

    def test_preview_rejects_insufficient_stock(self):
        with self.assertRaises(ValidationError):
            compute_sale_preview(
                cashier=self.cashier,
                items=[{"product_id": self.product.pk, "quantity": 999}],
                payment_method=Sale.PaymentMethod.CASH,
                paid_amount=Decimal("99900.00"),
            )

    def test_checkout_preview_view_returns_html_without_saving(self):
        self.client.login(username="preview_cashier", password="pass1234")
        response = self.client.post(
            "/sales/pos/checkout-preview/",
            {
                "customer_name": "",
                "customer_phone": "",
                "payment_method": "cash",
                "paid_amount": "200.00",
                "redeemed_points": "0",
                "discount": "0",
                "note": "",
                "lane_name": "checkout_a",
                "items_json": f'[{{"product_id": {self.product.pk}, "quantity": 2, "unit_price": "100.00"}}]',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preview Item")
        self.assertEqual(Sale.objects.count(), 0)

    def test_preview_then_confirm_only_commits_on_real_submit(self):
        self.client.login(username="preview_cashier", password="pass1234")
        payload = {
            "customer_name": "",
            "customer_phone": "",
            "payment_method": "cash",
            "paid_amount": "200.00",
            "redeemed_points": "0",
            "discount": "0",
            "note": "",
            "lane_name": "checkout_a",
            "items_json": f'[{{"product_id": {self.product.pk}, "quantity": 2, "unit_price": "100.00"}}]',
        }

        preview_response = self.client.post("/sales/pos/checkout-preview/", payload)
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(Sale.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)

        confirm_response = self.client.post("/sales/pos/", payload)
        self.assertEqual(confirm_response.status_code, 302)
        self.assertIn("autoprint=1", confirm_response.url)
        self.assertEqual(Sale.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 8)

    def test_checkout_preview_view_reports_stock_error(self):
        self.client.login(username="preview_cashier", password="pass1234")
        response = self.client.post(
            "/sales/pos/checkout-preview/",
            {
                "customer_name": "",
                "customer_phone": "",
                "payment_method": "cash",
                "paid_amount": "99900.00",
                "redeemed_points": "0",
                "discount": "0",
                "note": "",
                "lane_name": "checkout_a",
                "items_json": f'[{{"product_id": {self.product.pk}, "quantity": 999, "unit_price": "100.00"}}]',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "unit(s) left", status_code=400)


class PosTerminalCheckoutFormBindingTests(TestCase):
    def test_checkout_script_targets_sale_form_not_logout_form(self):
        branch = Branch.objects.create(name="POS Branch", code="pos-branch")
        cashier = User.objects.create_user(
            username="pos_checkout_cashier",
            password="pass1234",
            role=User.Role.CASHIER,
            branch=branch,
        )

        self.client.login(username=cashier.username, password="pass1234")
        response = self.client.get("/sales/pos/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form method="post" action="/accounts/logout/">')
        self.assertContains(response, '<form id="checkoutForm" method="post"')
        self.assertContains(response, "document.getElementById('checkoutForm')")
        self.assertNotContains(response, "document.querySelector('form[method=\"post\"]')")


class PosTerminalLowStockIndicatorTests(TestCase):
    def test_low_stock_product_gets_amber_border(self):
        branch = Branch.objects.create(name="Main", code="main2")
        admin = User.objects.create_user(username="pos_admin", password="pass1234", role=User.Role.ADMIN, is_staff=True)
        category = Category.objects.create(name="Snacks2")
        low_stock_product = Product.objects.create(
            name="LowStockItem", category=category, cost_price=Decimal("10.00"), selling_price=Decimal("20.00"),
            quantity=2, reorder_level=10,
        )
        BranchStock.objects.create(branch=branch, product=low_stock_product, quantity=2)

        self.client.login(username="pos_admin", password="pass1234")
        response = self.client.get("/sales/pos/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "border-l-amber-400")
