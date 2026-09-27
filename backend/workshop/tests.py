from decimal import Decimal
from datetime import datetime, date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from workshop.models import (
    Customer, Order, Job, Worker, WorkerSkill, GoldPurity,
    JobOverallStatus, StageCode, GoldTransaction, GoldTransactionType,
    Stone, StoneType, StoneTransaction, StoneTransactionType,
    QualityCheck, QCResult, Payment, BackupRecord
)
from workshop.services import export_jobs_to_excel, export_gold_ledger_to_excel, perform_system_backup

class GSCMSTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='testadmin', password='testpassword', email='admin@test.com')
        self.client = Client()
        self.client.login(username='testadmin', password='testpassword')

        self.customer = Customer.objects.create(
            name="Test Client",
            mobile="+91 99999 11111",
            address="Hyderabad"
        )

        self.worker = Worker.objects.create(
            worker_id="WRK-TEST-1",
            name="Master Karigar",
            phone="+91 88888 22222",
            specialization=WorkerSkill.GOLD_MAKING
        )

    def test_customer_creation_and_auto_id(self):
        self.assertTrue(self.customer.customer_id.startswith("CUST-2026-"))
        self.assertEqual(self.customer.total_orders, 0)

    def test_order_creation_and_item_splitting(self):
        order = Order.objects.create(
            customer=self.customer,
            total_estimated_amount=Decimal('50000.00'),
            advance_paid=Decimal('20000.00')
        )
        self.assertTrue(order.order_number.startswith("ORD-2026-"))
        self.assertEqual(order.balance_amount, Decimal('30000.00'))

        # Split Job A
        job_a = Job.objects.create(
            order=order,
            title="22K Peacock Ring",
            expected_weight=Decimal('10.500'),
            current_worker=self.worker
        )
        # Split Job B
        job_b = Job.objects.create(
            order=order,
            title="22K Matching Earrings",
            expected_weight=Decimal('15.000'),
            current_worker=self.worker
        )

        self.assertEqual(order.jobs.count(), 2)
        self.assertTrue(job_a.job_id.startswith("J-2026-"))
        self.assertIsNotNone(job_a.qr_code_image)

    def test_delayed_job_calculation(self):
        order = Order.objects.create(customer=self.customer)
        # Target was 2 hours ago
        past_target = timezone.now() - timedelta(hours=2)
        delayed_job = Job.objects.create(
            order=order,
            title="Delayed Pendant",
            target_date=past_target,
            overall_status=JobOverallStatus.IN_PROGRESS
        )
        self.assertTrue(delayed_job.is_delayed)
        self.assertIn("h", delayed_job.delay_duration)

    def test_gold_accountability_transactions(self):
        order = Order.objects.create(customer=self.customer)
        job = Job.objects.create(order=order, title="Gold Chain")

        # 1. Issue 20 grams
        GoldTransaction.objects.create(
            job=job,
            worker=self.worker,
            transaction_type=GoldTransactionType.GOLD_ISSUED,
            weight_grams=Decimal('20.000'),
            created_by=self.user
        )
        # 2. Return 18.5 grams finished + 1.2 grams scrap
        GoldTransaction.objects.create(
            job=job,
            worker=self.worker,
            transaction_type=GoldTransactionType.FINISHED_RETURNED,
            weight_grams=Decimal('18.500'),
            created_by=self.user
        )
        GoldTransaction.objects.create(
            job=job,
            worker=self.worker,
            transaction_type=GoldTransactionType.SCRAP_RETURNED,
            weight_grams=Decimal('1.200'),
            created_by=self.user
        )

        self.assertEqual(job.gold_issued_total, Decimal('20.000'))
        self.assertEqual(job.gold_returned_total, Decimal('19.700'))
        self.assertEqual(job.gold_balance_difference, Decimal('0.300')) # Melting loss / unaccounted

    def test_stone_inventory_deduction(self):
        stone = Stone.objects.create(
            stone_code="TEST-DIA",
            stone_type=StoneType.DIAMOND,
            total_quantity=50,
            available_quantity=50
        )
        order = Order.objects.create(customer=self.customer)
        job = Job.objects.create(order=order, title="Diamond Ring")

        # Allocate 10 stones
        response = self.client.post('/stones/', {
            'issue_stone': '1',
            'stone_id': stone.pk,
            'job_id': job.job_id,
            'worker_id': self.worker.pk,
            'quantity': '10',
            'weight_carats': '0.300'
        })
        self.assertEqual(response.status_code, 302)
        stone.refresh_from_db()
        self.assertEqual(stone.available_quantity, 40)

    def test_quality_check_pass_and_rework(self):
        order = Order.objects.create(customer=self.customer)
        job = Job.objects.create(order=order, title="QC Test Ring", current_stage=StageCode.QUALITY_CHECK)

        # Submit QC Pass
        response = self.client.post(f'/qc/{job.job_id}/', {
            'chk_design': 'on',
            'chk_weight': 'on',
            'chk_dimensions': 'on',
            'chk_stones': 'on',
            'chk_scratches': 'on',
            'chk_polish': 'on',
            'chk_solder': 'on',
            'chk_locks': 'on',
            'chk_finish': 'on',
            'chk_photo': 'on',
            'result': 'PASS'
        })
        self.assertEqual(response.status_code, 302)
        job.refresh_from_db()
        self.assertEqual(job.overall_status, JobOverallStatus.READY)
        self.assertEqual(job.current_stage, StageCode.READY)

    def test_excel_exports(self):
        job_excel = export_jobs_to_excel()
        self.assertGreater(job_excel.getbuffer().nbytes, 1000)

        gold_excel = export_gold_ledger_to_excel()
        self.assertGreater(gold_excel.getbuffer().nbytes, 1000)

    def test_backup_service(self):
        backup_record = perform_system_backup("Automated test backup")
        self.assertEqual(backup_record.status, "SUCCESS")
        self.assertGreater(backup_record.file_size_bytes, 100)

    def test_soft_delete_and_recycle_bin(self):
        # 1. Soft delete customer
        response = self.client.post(f'/delete/customer/{self.customer.pk}/')
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_deleted)

        # Active customer list context should not contain deleted customer
        list_response = self.client.get('/customers/')
        self.assertNotIn(self.customer, list_response.context['customers'])
        self.assertContains(list_response, "No customers found")

        # Recycle bin should contain deleted customer
        bin_response = self.client.get('/recycle-bin/')
        self.assertContains(bin_response, self.customer.name)

        # Restore from recycle bin
        restore_response = self.client.post(f'/recycle-bin/restore/customer/{self.customer.pk}/')
        self.assertEqual(restore_response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_deleted)

        # Active customer list should contain restored customer
        list_response_after = self.client.get('/customers/')
        self.assertContains(list_response_after, self.customer.name)

    def test_customer_edit(self):
        response = self.client.post(f'/customers/{self.customer.pk}/edit/', {
            'name': 'Updated Client Name',
            'mobile': '+91 98888 77777',
            'alternate_mobile': '+91 97777 66666',
            'email': 'updated@test.com',
            'address': 'Bangalore Indiranagar',
            'notes': 'High priority customer'
        })
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, 'Updated Client Name')
        self.assertEqual(self.customer.mobile, '+91 98888 77777')
        self.assertEqual(self.customer.alternate_mobile, '+91 97777 66666')

    def test_job_dossier_qr_view(self):
        order = Order.objects.create(customer=self.customer)
        job = Job.objects.create(
            order=order,
            title="Antique Gold Bangle",
            expected_weight=Decimal('24.500'),
            current_worker=self.worker
        )
        response = self.client.get(f'/jobs/{job.job_id}/dossier/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Antique Gold Bangle")
        self.assertContains(response, self.customer.name)
        self.assertContains(response, self.customer.mobile)
        self.assertContains(response, "SCAN ITEM QR")

    def test_live_rates_api(self):
        response = self.client.get('/api/live-rates/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('chennai', data)
        self.assertIn('bangalore', data)
        self.assertGreater(data['chennai']['gold_24k'], 5000)
        self.assertGreater(data['chennai']['gold_22k'], 5000)
        self.assertGreater(data['chennai']['silver_per_gram'], 50)
        self.assertGreater(data['bangalore']['gold_24k'], 5000)
        self.assertGreater(data['bangalore']['gold_22k'], 5000)
        self.assertGreater(data['bangalore']['silver_per_gram'], 50)

