import os
import shutil
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files import File
from django.utils import timezone
from django.conf import settings

from workshop.models import (
    UserProfile, UserRole, WorkshopSettings, Worker, WorkerSkill,
    Customer, Order, OrderType, PriorityLevel, OrderStatus,
    Job, JewelleryType, GoldPurity, JobOverallStatus, PhysicalLocation,
    StageCode, JobStageHistory, StageStatus, JobPhoto, PhotoCategory,
    GoldTransaction, GoldTransactionType, Stone, StoneType, StoneShape,
    StoneTransaction, StoneTransactionType, QualityCheck, QCResult,
    Payment, PaymentMethod, PaymentType, Delivery, Expense, ExpenseCategory,
    Notification, NotificationType, AuditLog
)

class Command(BaseCommand):
    help = 'Populates the workshop database with comprehensive, realistic production data.'

    def handle(self, *args, **options):
        self.stdout.write("Starting workshop data seeding...")

        # 1. Admin & Owner
        owner_user, _ = User.objects.get_or_create(
            username='owner',
            defaults={
                'first_name': 'Rahul',
                'last_name': 'Achari',
                'email': 'owner@swarnajewellers.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        owner_user.set_password('admin123')
        owner_user.save()
        UserProfile.objects.update_or_create(user=owner_user, defaults={'role': UserRole.OWNER, 'phone': '+91 98480 11223'})

        manager_user, _ = User.objects.get_or_create(
            username='manager',
            defaults={
                'first_name': 'Venkat',
                'last_name': 'Sharma',
                'email': 'manager@swarnajewellers.com',
                'is_staff': True
            }
        )
        manager_user.set_password('manager123')
        manager_user.save()
        UserProfile.objects.update_or_create(user=manager_user, defaults={'role': UserRole.MANAGER, 'phone': '+91 98480 33445'})

        # 2. Workshop Settings
        w_settings, _ = WorkshopSettings.objects.get_or_create(
            id=1,
            defaults={
                'name': 'Sri Swarna Artisan Goldsmiths & Fine Atelier',
                'tagline': 'Bespoke Traditional & Contemporary Fine Jewellery Workshop',
                'address': 'No. 44, Goldsmiths Guild Enclave, Jewellers Lane, Hyderabad - 500002',
                'phone': '+91 98480 22334',
                'email': 'craft@swarnajewellers.com',
                'currency_symbol': '₹',
                'default_purity': '22K',
                'gst_number': '36AAAFS1234D1Z2'
            }
        )

        # 3. Workers / Karigars
        workers_data = [
            ("WRK-001", "Ramesh Karigar", "+91 94401 23456", WorkerSkill.GOLD_MAKING, "Gold Melting, Die Making, Handcrafted Filigree, Sheet Rolling"),
            ("WRK-002", "Suresh Kumar", "+91 94401 34567", WorkerSkill.STONE_SETTING, "Prong, Pavé, Channel, Bezel, Micro-pavé Setting"),
            ("WRK-003", "Mahesh Babu", "+91 94401 45678", WorkerSkill.POLISHING, "Mirror Lapping, Steam Cleaning, Ultrasonic, Rhodium Plating"),
            ("WRK-004", "Ravi Achari", "+91 94401 56789", WorkerSkill.FILING, "Master Filing, Precision Piercing, Soldering, Hinges & Joints"),
        ]

        worker_objs = {}
        for wid, wname, wphone, wspec, wskills in workers_data:
            uname = wid.lower().replace('-', '_')
            u, _ = User.objects.get_or_create(username=uname, defaults={'first_name': wname.split()[0], 'last_name': wname.split()[1] if len(wname.split()) > 1 else ''})
            u.set_password('worker123')
            u.save()
            UserProfile.objects.update_or_create(user=u, defaults={'role': UserRole.KARIGAR, 'phone': wphone})
            w, _ = Worker.objects.get_or_create(
                worker_id=wid,
                defaults={'user': u, 'name': wname, 'phone': wphone, 'specialization': wspec, 'skills': wskills, 'joining_date': date(2023, 1, 15)}
            )
            worker_objs[wid] = w

        # 4. Customers
        customers_data = [
            ("CUST-2026-0001", "Ravi Kumar", "+91 98490 12345", "ravi.kumar@example.com", "Plot 42, Jubilee Hills, Hyderabad", "VIP Client. Prefers traditional 22K 916 Hallmark."),
            ("CUST-2026-0002", "Lakshmi Devi", "+91 98490 23456", "lakshmi.devi@example.com", "12-8, Banjara Hills, Hyderabad", "Regular wedding client. Has family legacy gold."),
            ("CUST-2026-0003", "Suresh Varma", "+91 98490 34567", "suresh.varma@example.com", "Kukatpally Housing Board, Hyderabad", "Custom bespoke designer rings."),
            ("CUST-2026-0004", "Priya Reddy", "+91 98490 45678", "priya.reddy@example.com", "Madhapur, Hitec City, Hyderabad", "Contemporary diamond bridal suite order."),
            ("CUST-2026-0005", "Anand Rao", "+91 98490 56789", "anand.rao@example.com", "Himayatnagar, Hyderabad", "Antique Temple jewellery collector."),
        ]

        customer_objs = {}
        for cid, cname, cmobile, cemail, caddr, cnotes in customers_data:
            c, _ = Customer.objects.get_or_create(
                customer_id=cid,
                defaults={'name': cname, 'mobile': cmobile, 'email': cemail, 'address': caddr, 'notes': cnotes}
            )
            customer_objs[cid] = c

        # 5. Stone Inventory
        stones_data = [
            ("STN-DIA-VVS-20", StoneType.DIAMOND, StoneShape.ROUND, "2.0 mm (0.03 ct)", 150, 94, Decimal('4.500'), "VVS-EF Natural", Decimal('1800.00'), "Stone Safe Box A"),
            ("STN-DIA-SOL-1CT", StoneType.DIAMOND, StoneShape.ROUND, "6.5 mm (1.00 ct)", 5, 2, Decimal('5.000'), "VVS1-D GIA Certified", Decimal('225000.00'), "Safe Vault Locker 1"),
            ("STN-RUBY-OVAL", StoneType.RUBY, StoneShape.OVAL, "6x4 mm (0.80 ct)", 30, 22, Decimal('24.000'), "Natural Burma Unheated", Decimal('12500.00'), "Stone Safe Box B"),
            ("STN-EMR-OCT-ZAM", StoneType.EMERALD, StoneShape.EMERALD_CUT, "8x6 mm (1.75 ct)", 12, 7, Decimal('21.000'), "Zambian Vivid Green", Decimal('34000.00'), "Stone Safe Box B"),
            ("STN-CZ-SWAR-RD", StoneType.CZ_STONE, StoneShape.ROUND, "1.5 mm", 500, 420, Decimal('10.000'), "Signity AAA", Decimal('25.00'), "Bench Drawer 4"),
            ("STN-PEARL-BASRA", StoneType.PEARL, StoneShape.ROUND, "4.0 mm South Sea", 80, 56, Decimal('32.000'), "Natural Basra Luster", Decimal('1200.00'), "Pearl Drawer 2"),
        ]
        stone_objs = {}
        for scode, stype, sshape, ssize, sqty, savail, swt, sgrade, scost, sloc in stones_data:
            st, _ = Stone.objects.get_or_create(
                stone_code=scode,
                defaults={
                    'stone_type': stype, 'shape': sshape, 'size_mm': ssize,
                    'total_quantity': sqty, 'available_quantity': savail,
                    'weight_carats': swt, 'grade': sgrade, 'cost_per_unit': scost,
                    'location': sloc
                }
            )
            stone_objs[scode] = st

        # Sample image paths from static
        sample_img_dir = os.path.join(settings.ROOT_DIR, "frontend", "static", "img", "sample_jewellery")

        def attach_photo(job, filename, category, caption):
            src_path = os.path.join(sample_img_dir, filename)
            if os.path.exists(src_path):
                with open(src_path, 'rb') as f:
                    jp = JobPhoto(
                        job=job,
                        category=category,
                        design_version=job.design_version,
                        caption=caption,
                        uploaded_by=owner_user
                    )
                    jp.image.save(filename, File(f), save=True)

        now = timezone.now()

        # 6. Orders and Split Jobs
        # --- ORDER 1: Ravi Kumar - 22K Peacock Antique Ring & Matching Earrings ---
        ord1, _ = Order.objects.get_or_create(
            order_number="ORD-2026-000101",
            defaults={
                'customer': customer_objs["CUST-2026-0001"],
                'order_type': OrderType.CUSTOM_ORDER,
                'priority': PriorityLevel.NORMAL,
                'status': OrderStatus.IN_PROGRESS,
                'total_estimated_amount': Decimal('145000.00'),
                'advance_paid': Decimal('50000.00'),
                'customer_instructions': "Traditional Peacock motif with natural ruby eye and fine South Indian nakshi work. Ring size 16.",
                'internal_notes': "Customer approved Design V1 sketch on WhatsApp.",
                'required_delivery_date': (now + timedelta(days=2)).date()
            }
        )

        job1a, _ = Job.objects.get_or_create(
            job_id="J-2026-000101-A",
            defaults={
                'order': ord1,
                'jewellery_type': JewelleryType.RING,
                'title': "22K Peacock Antique Nakshi Ring",
                'quantity': 1,
                'gold_purity': GoldPurity.P_22K,
                'expected_weight': Decimal('14.500'),
                'current_stage': StageCode.STONE_SETTING,
                'current_worker': worker_objs["WRK-002"],
                'current_location': PhysicalLocation.STONE_BENCH,
                'overall_status': JobOverallStatus.IN_PROGRESS,
                'priority': PriorityLevel.NORMAL,
                'customer_approved': True,
                'approved_at': now - timedelta(days=2),
                'approved_by': "Ravi Kumar (WhatsApp)",
                'start_date': now - timedelta(days=2),
                'target_date': now + timedelta(hours=6),
                'special_instructions': "Bezel set 1pc Burmese Ruby for peacock eye, pavé set small CZ on feathers."
            }
        )
        if not job1a.photos.exists():
            attach_photo(job1a, "peacock_ring_ref.jpg", PhotoCategory.REFERENCE_SKETCH, "Customer Hand Sketch V1")
            attach_photo(job1a, "peacock_ring_final.jpg", PhotoCategory.FINAL_FRONT, "Completed Nakshi Peacock Ring")

        # Stage histories for Job 1A
        JobStageHistory.objects.get_or_create(
            job=job1a, stage_name=StageCode.ORDER_RECEIVED,
            defaults={'status': StageStatus.COMPLETED, 'worker': None, 'actual_duration_minutes': 30, 'completion_time': now - timedelta(days=2)}
        )
        JobStageHistory.objects.get_or_create(
            job=job1a, stage_name=StageCode.MAKING,
            defaults={'status': StageStatus.COMPLETED, 'worker': worker_objs["WRK-001"], 'actual_duration_minutes': 280, 'start_time': now - timedelta(days=2), 'completion_time': now - timedelta(days=1)}
        )
        JobStageHistory.objects.get_or_create(
            job=job1a, stage_name=StageCode.STONE_SETTING,
            defaults={'status': StageStatus.IN_PROGRESS, 'worker': worker_objs["WRK-002"], 'start_time': now - timedelta(hours=3), 'target_hours': Decimal('4.00')}
        )

        # Gold transactions for Job 1A
        GoldTransaction.objects.get_or_create(
            transaction_id="GLD-202609-0001",
            defaults={
                'job': job1a,
                'worker': worker_objs["WRK-001"],
                'transaction_type': GoldTransactionType.GOLD_ISSUED,
                'purity': GoldPurity.P_22K,
                'weight_grams': Decimal('16.200'),
                'balance_after_grams': Decimal('16.200'),
                'notes': "Issued 22K 916 wire & granules for Peacock Ring casting & making",
                'created_by': owner_user
            }
        )
        GoldTransaction.objects.get_or_create(
            transaction_id="GLD-202609-0002",
            defaults={
                'job': job1a,
                'worker': worker_objs["WRK-001"],
                'transaction_type': GoldTransactionType.SCRAP_RETURNED,
                'purity': GoldPurity.P_22K,
                'weight_grams': Decimal('1.450'),
                'balance_after_grams': Decimal('14.750'),
                'notes': "Filing & cut sprue scrap returned from making bench",
                'created_by': owner_user
            }
        )

        # Stone transactions for Job 1A
        StoneTransaction.objects.get_or_create(
            job=job1a,
            stone=stone_objs["STN-RUBY-OVAL"],
            transaction_type=StoneTransactionType.ISSUE,
            defaults={'worker': worker_objs["WRK-002"], 'quantity': 1, 'weight_carats': Decimal('0.800'), 'notes': "Issued for peacock eye", 'created_by': owner_user}
        )

        # Split Job 1B: Peacock Earrings
        job1b, _ = Job.objects.get_or_create(
            job_id="J-2026-000101-B",
            defaults={
                'order': ord1,
                'jewellery_type': JewelleryType.EARRINGS,
                'title': "22K Matching Peacock Drop Earrings (Pair)",
                'quantity': 1,
                'gold_purity': GoldPurity.P_22K,
                'expected_weight': Decimal('18.000'),
                'current_stage': StageCode.MAKING,
                'current_worker': worker_objs["WRK-001"],
                'current_location': PhysicalLocation.MAKING_TABLE_1,
                'overall_status': JobOverallStatus.IN_PROGRESS,
                'priority': PriorityLevel.NORMAL,
                'customer_approved': True,
                'start_date': now - timedelta(days=1),
                'target_date': now + timedelta(days=1, hours=4),
                'special_instructions': "Matching drops to ring design. South Indian screw back."
            }
        )
        if not job1b.photos.exists():
            attach_photo(job1b, "peacock_ring_ref.jpg", PhotoCategory.REFERENCE_SKETCH, "Earrings Matching Sketch")

        # --- ORDER 2: Priya Reddy - VVS Diamond Bridal Choker (DELAYED JOB FOR ALERT DEMO) ---
        ord2, _ = Order.objects.get_or_create(
            order_number="ORD-2026-000102",
            defaults={
                'customer': customer_objs["CUST-2026-0004"],
                'order_type': OrderType.NEW_JEWELLERY,
                'priority': PriorityLevel.URGENT,
                'status': OrderStatus.IN_PROGRESS,
                'total_estimated_amount': Decimal('385000.00'),
                'advance_paid': Decimal('150000.00'),
                'customer_instructions': "Requires high precision micro-prong setting. Delivery promised strictly for wedding muhurtham.",
                'required_delivery_date': (now + timedelta(days=1)).date()
            }
        )

        # Delay is set 1 hour 25 mins ago!
        delayed_target = now - timedelta(hours=1, minutes=25)
        job2, _ = Job.objects.get_or_create(
            job_id="J-2026-000102-A",
            defaults={
                'order': ord2,
                'jewellery_type': JewelleryType.NECKLACE,
                'title': "18K VVS Diamond Bridal Choker",
                'quantity': 1,
                'gold_purity': GoldPurity.P_18K,
                'expected_weight': Decimal('48.500'),
                'current_stage': StageCode.STONE_SETTING,
                'current_worker': worker_objs["WRK-002"],
                'current_location': PhysicalLocation.STONE_BENCH,
                'overall_status': JobOverallStatus.IN_PROGRESS,
                'priority': PriorityLevel.URGENT,
                'customer_approved': True,
                'start_date': now - timedelta(days=3),
                'target_date': delayed_target, # Automatically triggers "DELAYED BY 1h 25m"
                'special_instructions': "Pavé setting 94 diamonds. Extra microscope inspection required."
            }
        )
        if not job2.photos.exists():
            attach_photo(job2, "diamond_necklace_ref.jpg", PhotoCategory.CUSTOMER_REF, "Customer Inspiration WhatsApp Blueprint")
            attach_photo(job2, "diamond_necklace_final.jpg", PhotoCategory.FINAL_FRONT, "Choker on Vitrine Stand")

        JobStageHistory.objects.get_or_create(
            job=job2, stage_name=StageCode.STONE_SETTING,
            defaults={
                'status': StageStatus.IN_PROGRESS,
                'worker': worker_objs["WRK-002"],
                'start_time': now - timedelta(hours=6),
                'target_hours': Decimal('4.00'),
                'notes': "Karigar taking extra time on delicate prong alignment."
            }
        )

        Notification.objects.get_or_create(
            job=job2,
            notification_type=NotificationType.DELAYED,
            defaults={
                'title': f"DELAYED: Job {job2.job_id} is overdue by 1h 25m",
                'message': f"Assigned Karigar Suresh Kumar is setting stones on {job2.title}. Target was {delayed_target.strftime('%I:%M %p')}.",
                'is_read': False
            }
        )

        # --- ORDER 3: Lakshmi Devi - 22K Temple Bangle (Polishing) ---
        ord3, _ = Order.objects.get_or_create(
            order_number="ORD-2026-000103",
            defaults={
                'customer': customer_objs["CUST-2026-0002"],
                'order_type': OrderType.NEW_JEWELLERY,
                'priority': PriorityLevel.IMPORTANT,
                'status': OrderStatus.IN_PROGRESS,
                'total_estimated_amount': Decimal('320000.00'),
                'advance_paid': Decimal('100000.00'),
                'customer_instructions': "Lakshmi motif kada. Antique matte gold finish with glossy highlighted borders.",
                'required_delivery_date': (now + timedelta(days=3)).date()
            }
        )
        job3, _ = Job.objects.get_or_create(
            job_id="J-2026-000103-A",
            defaults={
                'order': ord3,
                'jewellery_type': JewelleryType.BANGLE,
                'title': "22K Hand-Engraved Lakshmi Temple Bangle (45g)",
                'quantity': 1,
                'gold_purity': GoldPurity.P_22K,
                'expected_weight': Decimal('45.000'),
                'current_stage': StageCode.POLISHING,
                'current_worker': worker_objs["WRK-003"],
                'current_location': PhysicalLocation.POLISH_ROOM,
                'overall_status': JobOverallStatus.IN_PROGRESS,
                'priority': PriorityLevel.IMPORTANT,
                'customer_approved': True,
                'start_date': now - timedelta(days=2),
                'target_date': now + timedelta(hours=4),
                'special_instructions': "Antique patina wash followed by high-point wheel buffing."
            }
        )
        if not job3.photos.exists():
            attach_photo(job3, "temple_bangle_ref.jpg", PhotoCategory.REFERENCE_SKETCH, "Temple Bangle Blueprint")
            attach_photo(job3, "temple_bangle_final.jpg", PhotoCategory.FINAL_FRONT, "Handcrafted Temple Kada Finished")

        # --- ORDER 4: Suresh Varma - Natural Emerald Pendant (QC DESK) ---
        ord4, _ = Order.objects.get_or_create(
            order_number="ORD-2026-000104",
            defaults={
                'customer': customer_objs["CUST-2026-0003"],
                'order_type': OrderType.CUSTOM_ORDER,
                'priority': PriorityLevel.NORMAL,
                'status': OrderStatus.IN_PROGRESS,
                'total_estimated_amount': Decimal('115000.00'),
                'advance_paid': Decimal('60000.00'),
                'customer_instructions': "18K Yellow Gold Zambian Emerald pendant with hidden bail.",
                'required_delivery_date': (now + timedelta(days=1)).date()
            }
        )
        job4, _ = Job.objects.get_or_create(
            job_id="J-2026-000104-A",
            defaults={
                'order': ord4,
                'jewellery_type': JewelleryType.PENDANT,
                'title': "18K Zambian Emerald Halo Pendant",
                'quantity': 1,
                'gold_purity': GoldPurity.P_18K,
                'expected_weight': Decimal('8.200'),
                'current_stage': StageCode.QUALITY_CHECK,
                'current_worker': None,
                'current_location': PhysicalLocation.QC_DESK,
                'overall_status': JobOverallStatus.QC_PENDING,
                'priority': PriorityLevel.NORMAL,
                'customer_approved': True,
                'start_date': now - timedelta(days=4),
                'target_date': now + timedelta(hours=2),
                'final_gross_weight': Decimal('9.950'),
                'net_gold_weight': Decimal('8.200'),
                'stone_weight': Decimal('1.750'),
            }
        )
        if not job4.photos.exists():
            attach_photo(job4, "emerald_pendant_ref.jpg", PhotoCategory.REFERENCE_SKETCH, "Pendant Drawing")
            attach_photo(job4, "emerald_pendant_final.jpg", PhotoCategory.FINAL_FRONT, "Finished Emerald Halo Pendant")

        # Quality Check for Job 4
        QualityCheck.objects.get_or_create(
            job=job4,
            defaults={
                'inspected_by': owner_user,
                'design_matches': True,
                'correct_weight': True,
                'correct_dimensions': True,
                'stones_properly_fitted': True,
                'no_visible_scratches': True,
                'polishing_completed': True,
                'soldering_checked': True,
                'locks_hooks_checked': True,
                'finish_checked': True,
                'final_photo_uploaded': True,
                'result': QCResult.PASS,
                'notes': "Flawless mirror finish and secure prong grip around the natural Zambian emerald."
            }
        )

        # --- ORDER 5: Ready for Delivery ---
        ord5, _ = Order.objects.get_or_create(
            order_number="ORD-2026-000105",
            defaults={
                'customer': customer_objs["CUST-2026-0005"],
                'order_type': OrderType.NEW_JEWELLERY,
                'priority': PriorityLevel.NORMAL,
                'status': OrderStatus.IN_PROGRESS,
                'total_estimated_amount': Decimal('85000.00'),
                'advance_paid': Decimal('85000.00'),
                'balance_amount': Decimal('0.00'),
                'customer_instructions': "Guttapusalu style drops with seed pearls.",
                'required_delivery_date': now.date()
            }
        )
        job5, _ = Job.objects.get_or_create(
            job_id="J-2026-000105-A",
            defaults={
                'order': ord5,
                'jewellery_type': JewelleryType.NECKLACE,
                'title': "22K Traditional Guttapusalu Choker",
                'quantity': 1,
                'gold_purity': GoldPurity.P_22K,
                'expected_weight': Decimal('32.000'),
                'final_gross_weight': Decimal('34.200'),
                'net_gold_weight': Decimal('31.850'),
                'stone_weight': Decimal('2.350'),
                'current_stage': StageCode.READY,
                'current_location': PhysicalLocation.READY_DISPLAY,
                'overall_status': JobOverallStatus.READY,
                'customer_approved': True,
                'start_date': now - timedelta(days=5),
                'completion_date': now - timedelta(hours=1),
                'target_date': now,
            }
        )
        if not job5.photos.exists():
            attach_photo(job5, "diamond_necklace_final.jpg", PhotoCategory.FINAL_FRONT, "Choker Ready in Presentation Case")

        # 7. Payments
        Payment.objects.get_or_create(
            receipt_number="RCPT-2026-00001",
            defaults={
                'order': ord1,
                'customer': customer_objs["CUST-2026-0001"],
                'amount': Decimal('50000.00'),
                'payment_type': PaymentType.ADVANCE,
                'payment_method': PaymentMethod.UPI,
                'transaction_reference': "UPI/9849012345/TXN98234",
                'received_by': owner_user,
                'date': (now - timedelta(days=2)).date(),
                'notes': "Advance for 22K Peacock Ring & Earrings"
            }
        )
        Payment.objects.get_or_create(
            receipt_number="RCPT-2026-00002",
            defaults={
                'order': ord2,
                'customer': customer_objs["CUST-2026-0004"],
                'amount': Decimal('150000.00'),
                'payment_type': PaymentType.ADVANCE,
                'payment_method': PaymentMethod.BANK_TRANSFER,
                'transaction_reference': "IMPS-HDFC-9912049",
                'received_by': owner_user,
                'date': (now - timedelta(days=3)).date(),
                'notes': "Advance for Diamond Choker"
            }
        )
        Payment.objects.get_or_create(
            receipt_number="RCPT-2026-00003",
            defaults={
                'order': ord5,
                'customer': customer_objs["CUST-2026-0005"],
                'amount': Decimal('85000.00'),
                'payment_type': PaymentType.FINAL,
                'payment_method': PaymentMethod.CASH,
                'transaction_reference': "CASH-REC-105",
                'received_by': owner_user,
                'date': now.date(),
                'notes': "Full payment received at counter"
            }
        )

        # 8. Sample Workshop Expenses
        Expense.objects.get_or_create(
            title="Laser Soldering Machine Maintenance & Gas Refill",
            defaults={
                'category': ExpenseCategory.MAINTENANCE,
                'amount': Decimal('4800.00'),
                'date': (now - timedelta(days=4)).date(),
                'description': "Servicing of Nd:YAG laser welder and argon gas canister cylinder",
                'created_by': owner_user
            }
        )
        Expense.objects.get_or_create(
            title="Busch High-Speed Setting Burrs & Silicon Wheels",
            defaults={
                'category': ExpenseCategory.TOOLS,
                'amount': Decimal('6250.00'),
                'date': (now - timedelta(days=1)).date(),
                'description': "Ball burrs, hart burrs 0.8-2.5mm and green polishing wheels",
                'created_by': owner_user
            }
        )

        # 9. Audit Log entries
        AuditLog.objects.get_or_create(
            action="Order Created",
            model_name="Order",
            object_id=str(ord1.id),
            defaults={
                'user': owner_user,
                'object_repr': str(ord1),
                'details': "Order created with 2 split jobs: Peacock Ring & Matching Earrings",
                'ip_address': "127.0.0.1"
            }
        )
        AuditLog.objects.get_or_create(
            action="Gold Issued",
            model_name="GoldTransaction",
            object_id="GLD-202609-0001",
            defaults={
                'user': owner_user,
                'object_repr': "16.200g 22K issued to Ramesh Karigar for J-2026-000101-A",
                'details': "Purity: 22K 916 Hallmark granules & wire",
                'ip_address': "127.0.0.1"
            }
        )

        self.stdout.write(self.style.SUCCESS("Workshop seed data created successfully!"))
