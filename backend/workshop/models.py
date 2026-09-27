import os
import io
import qrcode
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.base import ContentFile
from django.urls import reverse
import re

def _generate_sequential_id(model_cls, field_name, prefix, digits=4, suffix_func=None):
    """
    Safely generates the next unique sequential ID by finding the maximum
    sequence number across all existing records, incrementing it, and verifying
    uniqueness so UNIQUE constraint collisions can never occur even after record deletions.
    """
    existing_vals = model_cls.objects.values_list(field_name, flat=True)
    pattern = re.compile(rf"{re.escape(prefix)}(\d+)")
    max_num = 0
    for val in existing_vals:
        if val:
            match = pattern.search(str(val))
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass

    candidate_num = max(max_num + 1, 1)
    while True:
        base_id = f"{prefix}{candidate_num:0{digits}d}"
        final_id = suffix_func(base_id, candidate_num) if suffix_func else base_id
        if not model_cls.objects.filter(**{field_name: final_id}).exists():
            return final_id
        candidate_num += 1

# --- ROLES & PERMISSIONS ---
class UserRole(models.TextChoices):
    OWNER = 'OWNER', 'Owner / Administrator'
    MANAGER = 'MANAGER', 'Production Manager'
    KARIGAR = 'KARIGAR', 'Karigar / Artisan'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
    CUSTOMER = 'CUSTOMER', 'Customer'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.KARIGAR)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class WorkshopSettings(models.Model):
    name = models.CharField(max_length=150, default="GSCMS")
    tagline = models.CharField(max_length=255, default="Jewellery & Goldsmith Workshop Management System", blank=True)
    address = models.TextField(default="12-4-56 Temple Street, Goldsmiths Lane, Jewellery Bazaar")
    phone = models.CharField(max_length=30, default="+91 98480 22334")
    email = models.EmailField(default="contact@swarnajewellers.com", blank=True)
    gst_number = models.CharField(max_length=30, default="37AAAAA0000A1Z5", blank=True)
    currency_symbol = models.CharField(max_length=10, default="₹")
    default_purity = models.CharField(max_length=10, default="22K")
    job_id_prefix = models.CharField(max_length=10, default="J-2026-")
    order_id_prefix = models.CharField(max_length=10, default="ORD-2026-")
    logo = models.ImageField(upload_to='settings/', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Workshop Settings"


# --- WORKER MANAGEMENT ---
class WorkerSkill(models.TextChoices):
    GOLD_MAKING = 'GOLD_MAKING', 'Gold Making'
    CASTING = 'CASTING', 'Casting'
    FILING = 'FILING', 'Filing & Shaping'
    SOLDERING = 'SOLDERING', 'Soldering & Assembly'
    STONE_SETTING = 'STONE_SETTING', 'Stone Setting'
    POLISHING = 'POLISHING', 'Polishing & Lapping'
    FINISHING = 'FINISHING', 'Finishing & Rhodium'
    QC = 'QC', 'Quality Control'
    REPAIR = 'REPAIR', 'Repair & Modification'

class Worker(models.Model):
    worker_id = models.CharField(max_length=30, unique=True)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='worker_record')
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=25)
    specialization = models.CharField(max_length=50, choices=WorkerSkill.choices, default=WorkerSkill.GOLD_MAKING)
    skills = models.CharField(max_length=255, blank=True, help_text="Comma-separated skills")
    is_active = models.BooleanField(default=True)
    joining_date = models.DateField(default=date.today)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.get_specialization_display()} ({self.worker_id})"

    @property
    def assigned_jobs_count(self):
        return self.assigned_jobs.filter(overall_status__in=['ASSIGNED', 'IN_PROGRESS', 'WAITING']).count()

    @property
    def completed_today_count(self):
        today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()
        return self.stage_histories.filter(status='COMPLETED', completion_time__date=today).count()

    @property
    def delayed_jobs_count(self):
        return self.assigned_jobs.filter(overall_status='IN_PROGRESS', is_delayed=True).count()


# --- CUSTOMER MANAGEMENT ---
class Customer(models.Model):
    customer_id = models.CharField(max_length=40, unique=True, blank=True)
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=25, db_index=True)
    alternate_mobile = models.CharField(max_length=25, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = _generate_sequential_id(Customer, 'customer_id', 'CUST-2026-', digits=4)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.mobile})"

    @property
    def total_orders(self):
        return self.orders.count()

    @property
    def active_orders(self):
        return self.orders.filter(status__in=['PENDING', 'IN_PROGRESS']).count()

    @property
    def completed_orders(self):
        return self.orders.filter(status='COMPLETED').count()

    @property
    def total_order_value(self):
        return sum(o.total_estimated_amount for o in self.orders.all()) or Decimal('0.00')

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments.all()) or Decimal('0.00')

    @property
    def outstanding_balance(self):
        balance = self.total_order_value - self.total_paid
        return max(Decimal('0.00'), balance)


class CustomerNote(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='customer_notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Note on {self.customer.name} at {self.created_at.strftime('%d/%m/%Y')}"


# --- WORKFLOW DEFINITION ---
class StageCode(models.TextChoices):
    ORDER_RECEIVED = 'ORDER_RECEIVED', 'Order Received'
    DESIGN_CONFIRMATION = 'DESIGN_CONFIRMATION', 'Design Confirmation'
    GOLD_ISSUED = 'GOLD_ISSUED', 'Gold Issued'
    MELTING = 'MELTING', 'Melting'
    CASTING = 'CASTING', 'Casting'
    MAKING = 'MAKING', 'Making / Handcrafting'
    FILING = 'FILING', 'Filing & Shaping'
    SOLDERING = 'SOLDERING', 'Soldering & Assembly'
    STONE_SETTING = 'STONE_SETTING', 'Stone Setting'
    POLISHING = 'POLISHING', 'Polishing & Lapping'
    FINISHING = 'FINISHING', 'Finishing & Rhodium'
    QUALITY_CHECK = 'QUALITY_CHECK', 'Quality Check (QC)'
    READY = 'READY', 'Ready for Delivery'
    DELIVERED = 'DELIVERED', 'Delivered'


# --- ORDER MANAGEMENT ---
class OrderType(models.TextChoices):
    NEW_JEWELLERY = 'NEW_JEWELLERY', 'New Jewellery'
    REPAIR = 'REPAIR', 'Repair'
    MODIFICATION = 'MODIFICATION', 'Modification'
    RE_POLISHING = 'RE_POLISHING', 'Re-polishing'
    STONE_REPLACEMENT = 'STONE_REPLACEMENT', 'Stone Replacement'
    RESIZING = 'RESIZING', 'Resizing'
    CUSTOM_ORDER = 'CUSTOM_ORDER', 'Custom Bespoke Order'
    OTHER = 'OTHER', 'Other'

class PriorityLevel(models.TextChoices):
    LOW = 'LOW', 'Low Priority'
    NORMAL = 'NORMAL', 'Normal'
    IMPORTANT = 'IMPORTANT', 'Important'
    URGENT = 'URGENT', 'Urgent'

class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    DELIVERED = 'DELIVERED', 'Delivered'
    CANCELLED = 'CANCELLED', 'Cancelled'

class Order(models.Model):
    order_number = models.CharField(max_length=40, unique=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    order_type = models.CharField(max_length=40, choices=OrderType.choices, default=OrderType.NEW_JEWELLERY)
    priority = models.CharField(max_length=20, choices=PriorityLevel.choices, default=PriorityLevel.NORMAL)
    status = models.CharField(max_length=30, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    advance_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    customer_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    required_delivery_date = models.DateField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = _generate_sequential_id(Order, 'order_number', 'ORD-2026-', digits=5)
        self.balance_amount = max(Decimal('0.00'), self.total_estimated_amount - self.advance_paid)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.customer.name}"

    @property
    def jobs_count(self):
        return self.jobs.count()

    @property
    def completed_jobs_count(self):
        return self.jobs.filter(overall_status__in=['READY', 'DELIVERED']).count()


# --- JEWELLERY JOBS & PRODUCTION ---
class JewelleryType(models.TextChoices):
    RING = 'RING', 'Ring'
    CHAIN = 'CHAIN', 'Chain'
    NECKLACE = 'NECKLACE', 'Necklace'
    BANGLE = 'BANGLE', 'Bangle'
    BRACELET = 'BRACELET', 'Bracelet'
    EARRINGS = 'EARRINGS', 'Earrings'
    PENDANT = 'PENDANT', 'Pendant'
    ANKLET = 'ANKLET', 'Anklet'
    NOSE_PIN = 'NOSE_PIN', 'Nose Pin'
    OTHER = 'OTHER', 'Other Jewellery'

class GoldPurity(models.TextChoices):
    P_24K = '24K', '24K (99.9%)'
    P_22K = '22K', '22K (91.6% Hallmark)'
    P_20K = '20K', '20K (83.3%)'
    P_18K = '18K', '18K (75.0%)'
    P_14K = '14K', '14K (58.5%)'
    OTHER = 'OTHER', 'Other Purity'

class JobOverallStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Assignment'
    ASSIGNED = 'ASSIGNED', 'Assigned'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    WAITING = 'WAITING', 'Waiting / On Hold'
    QC_PENDING = 'QC_PENDING', 'QC Pending'
    READY = 'READY', 'Ready for Delivery'
    DELIVERED = 'DELIVERED', 'Delivered'
    CANCELLED = 'CANCELLED', 'Cancelled'

class PhysicalLocation(models.TextChoices):
    OWNER_SAFE = 'OWNER_SAFE', 'Owner Safe / Vault'
    MAKING_TABLE_1 = 'MAKING_TABLE_1', 'Making Table 1 (Ramesh)'
    MAKING_TABLE_2 = 'MAKING_TABLE_2', 'Making Table 2 (Ravi)'
    STONE_BENCH = 'STONE_BENCH', 'Stone Setting Bench (Suresh)'
    POLISH_ROOM = 'POLISH_ROOM', 'Polishing Room (Mahesh)'
    QC_DESK = 'QC_DESK', 'Quality Inspection Desk'
    READY_DISPLAY = 'READY_DISPLAY', 'Ready Vitrine / Delivery Counter'
    CUSTOMER_HANDS = 'CUSTOMER_HANDS', 'Delivered to Customer'

class Job(models.Model):
    job_id = models.CharField(max_length=50, unique=True, db_index=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='jobs')
    jewellery_type = models.CharField(max_length=40, choices=JewelleryType.choices, default=JewelleryType.RING)
    title = models.CharField(max_length=200, help_text="e.g. 22K Peacock Antique Ring")
    quantity = models.PositiveIntegerField(default=1)
    gold_purity = models.CharField(max_length=20, choices=GoldPurity.choices, default=GoldPurity.P_22K)
    expected_weight = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'), help_text="In Grams")
    
    # Final weight accountability
    final_gross_weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Total finished weight in grams")
    net_gold_weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Net gold weight in grams")
    stone_weight = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True, help_text="Total stone weight in grams/carats")
    other_material_weight = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'), help_text="Wax, thread, enamel etc.")
    wastage_weight = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'), help_text="Recovered / melting loss in grams")
    
    custom_type_name = models.CharField(max_length=120, blank=True, help_text="Custom jewellery item name if Other")
    
    # Workflow tracking (Received -> Polisher -> Stone Fitter -> Completed)
    current_stage = models.CharField(max_length=50, choices=StageCode.choices, default=StageCode.ORDER_RECEIVED)
    atelier_stage = models.CharField(max_length=40, default='RECEIVED') # 'RECEIVED', 'AT_POLISHER', 'POLISH_DONE', 'AT_STONE', 'STONE_DONE', 'COMPLETED'
    polisher_given_date = models.DateTimeField(null=True, blank=True)
    polisher_received_date = models.DateTimeField(null=True, blank=True)
    stone_given_date = models.DateTimeField(null=True, blank=True)
    stone_received_date = models.DateTimeField(null=True, blank=True)
    current_worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs')
    current_location = models.CharField(max_length=50, choices=PhysicalLocation.choices, default=PhysicalLocation.OWNER_SAFE)
    overall_status = models.CharField(max_length=30, choices=JobOverallStatus.choices, default=JobOverallStatus.PENDING)
    priority = models.CharField(max_length=20, choices=PriorityLevel.choices, default=PriorityLevel.NORMAL)
    waiting_reason = models.CharField(max_length=255, blank=True, help_text="Reason if waiting/on hold")
    
    # Design revisions
    design_version = models.PositiveIntegerField(default=1)
    customer_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, blank=True)
    
    # Dates & Durations
    target_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    
    # QR Code
    qr_code_image = models.ImageField(upload_to='jobs/qr/', blank=True, null=True)
    
    special_instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_qr(self, base_url=""):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        # A QR code should open the live dossier when scanned by a phone camera.
        # Text records and relative paths are not clickable scanner results.
        dossier_path = reverse('job_dossier', kwargs={'job_id': self.job_id})
        qr_data = f"{base_url.rstrip('/')}{dossier_path}" if base_url else dossier_path
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0a0a0c", back_color="#ffffff")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        filename = f"qr_{self.job_id}.png"
        self.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        if not self.job_id:
            order_suffix = chr(ord('A') + (self.order.jobs.count() if self.order_id else 0))
            def add_job_suffix(base_id, num):
                return f"{base_id}-{order_suffix}"
            self.job_id = _generate_sequential_id(Job, 'job_id', 'J-2026-', digits=5, suffix_func=add_job_suffix)
        
        if not self.qr_code_image:
            self.generate_qr()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job_id} - {self.title} ({self.get_current_stage_display()})"

    @property
    def is_delayed(self):
        if self.overall_status in ['READY', 'DELIVERED', 'CANCELLED']:
            return False
        if not self.target_date:
            return False
        now = timezone.now()
        if timezone.is_naive(self.target_date):
            return datetime.now() > self.target_date
        return now > self.target_date

    @property
    def delay_duration(self):
        if not self.is_delayed:
            return None
        now = timezone.now()
        target = self.target_date
        if timezone.is_naive(target):
            diff = datetime.now() - target
        else:
            diff = now - target
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        if hours > 24:
            days = hours // 24
            return f"{days}d {hours % 24}h"
        return f"{hours}h {minutes}m"

    @property
    def reference_photo(self):
        try:
            photo = self.photos.filter(category__in=['REFERENCE', 'REFERENCE_FRONT', 'REFERENCE_SIDE', 'REFERENCE_BACK', 'REFERENCE_SKETCH', 'CUSTOMER_REF']).first()
            if photo and photo.image:
                return photo.image.url
        except Exception:
            return None
        return None

    @property
    def final_photo(self):
        try:
            photo = self.photos.filter(category__in=['FINAL_PIECE', 'FINAL_FRONT', 'FINAL_SIDE', 'FINAL_BACK', 'FINAL_CLOSEUP', 'STONE_DETAIL', 'PACKAGING']).first()
            if photo and photo.image:
                return photo.image.url
        except Exception:
            return None
        return None

    @property
    def gold_issued_total(self):
        return sum(t.weight_grams for t in self.gold_transactions.filter(transaction_type='GOLD_ISSUED')) or Decimal('0.000')

    @property
    def gold_returned_total(self):
        return sum(t.weight_grams for t in self.gold_transactions.filter(transaction_type__in=['FINISHED_RETURNED', 'SCRAP_RETURNED', 'DUST_RECOVERED'])) or Decimal('0.000')

    @property
    def gold_balance_difference(self):
        diff = self.gold_issued_total - self.gold_returned_total
        return round(diff, 3)


# --- WORK STAGE TRACKING & TIME ---
class StageStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ASSIGNED = 'ASSIGNED', 'Assigned'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    PAUSED = 'PAUSED', 'Paused'
    COMPLETED = 'COMPLETED', 'Completed'
    REJECTED = 'REJECTED', 'Rejected'
    REWORK_REQUIRED = 'REWORK_REQUIRED', 'Rework Required'

class JobStageHistory(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='stage_histories')
    stage_name = models.CharField(max_length=50, choices=StageCode.choices)
    worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True, related_name='stage_histories')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    
    start_time = models.DateTimeField(null=True, blank=True)
    pause_time = models.DateTimeField(null=True, blank=True)
    resume_time = models.DateTimeField(null=True, blank=True)
    completion_time = models.DateTimeField(null=True, blank=True)
    
    target_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('4.00'))
    actual_duration_minutes = models.PositiveIntegerField(default=0)
    
    status = models.CharField(max_length=30, choices=StageStatus.choices, default=StageStatus.PENDING)
    notes = models.TextField(blank=True)
    issue_report = models.TextField(blank=True)
    
    is_rework = models.BooleanField(default=False)
    rework_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['assigned_at']

    def calculate_actual_duration(self):
        if self.start_time and self.completion_time:
            diff = self.completion_time - self.start_time
            self.actual_duration_minutes = max(1, int(diff.total_seconds() // 60))
            self.save(update_fields=['actual_duration_minutes'])

    def __str__(self):
        worker_str = self.worker.name if self.worker else "Unassigned"
        return f"{self.job.job_id} - {self.get_stage_name_display()} ({worker_str})"


# --- PHOTO MANAGEMENT (REFERENCE, PROGRESS, FINAL) ---
class PhotoCategory(models.TextChoices):
    REFERENCE = 'REFERENCE', 'Customer Reference'
    REFERENCE_FRONT = 'REFERENCE_FRONT', 'Reference - Front View'
    REFERENCE_SIDE = 'REFERENCE_SIDE', 'Reference - Side View'
    REFERENCE_BACK = 'REFERENCE_BACK', 'Reference - Back View'
    REFERENCE_SKETCH = 'REFERENCE_SKETCH', 'Reference - Hand Sketch'
    CUSTOMER_REF = 'CUSTOMER_REF', 'Customer WhatsApp / Reference'
    PROGRESS = 'PROGRESS', 'Progress / In-Stage Photo'
    FINAL_PIECE = 'FINAL_PIECE', 'Final Finished Output'
    FINAL_FRONT = 'FINAL_FRONT', 'Final Finished - Front'
    FINAL_SIDE = 'FINAL_SIDE', 'Final Finished - Side'
    FINAL_BACK = 'FINAL_BACK', 'Final Finished - Back'
    FINAL_CLOSEUP = 'FINAL_CLOSEUP', 'Final Finished - Close-up & Hallmark'
    STONE_DETAIL = 'STONE_DETAIL', 'Stone & Setting Detail'
    PACKAGING = 'PACKAGING', 'Packaging & Box'
    OTHER = 'OTHER', 'Other'

def job_photo_upload_path(instance, filename):
    folder = "reference" if "REFERENCE" in instance.category or "CUSTOMER" in instance.category else ("final" if "FINAL" in instance.category else "progress")
    return f"jobs/{instance.job.job_id}/{folder}/{filename}"

class JobPhoto(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='photos')
    category = models.CharField(max_length=40, choices=PhotoCategory.choices, default=PhotoCategory.REFERENCE_FRONT)
    image = models.ImageField(upload_to=job_photo_upload_path)
    design_version = models.PositiveIntegerField(default=1)
    stage_name = models.CharField(max_length=50, blank=True)
    worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __init__(self, *args, **kwargs):
        if 'photo' in kwargs and 'image' not in kwargs:
            kwargs['image'] = kwargs.pop('photo')
        super().__init__(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job.job_id} - {self.get_category_display()}"


# --- GOLD MANAGEMENT & IMMUTABLE LEDGER ---
class GoldTransactionType(models.TextChoices):
    OPENING_BALANCE = 'OPENING_BALANCE', 'Opening Vault Balance'
    GOLD_RECEIVED = 'GOLD_RECEIVED', 'Gold Received (Bullion/Old Gold)'
    GOLD_ISSUED = 'GOLD_ISSUED', 'Gold Issued to Worker'
    FINISHED_RETURNED = 'FINISHED_RETURNED', 'Finished Item Gold Returned'
    SCRAP_RETURNED = 'SCRAP_RETURNED', 'Scrap Gold Returned'
    DUST_RECOVERED = 'DUST_RECOVERED', 'Polishing Dust / Vacuum Recovered'
    MELTING_LOSS = 'MELTING_LOSS', 'Melting / Fire Loss'
    REVERSAL_ADJUSTMENT = 'REVERSAL_ADJUSTMENT', 'Audit Adjustment / Reversal'

class GoldTransaction(models.Model):
    transaction_id = models.CharField(max_length=40, unique=True)
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='gold_transactions')
    worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True, related_name='gold_transactions')
    transaction_type = models.CharField(max_length=30, choices=GoldTransactionType.choices)
    purity = models.CharField(max_length=20, choices=GoldPurity.choices, default=GoldPurity.P_22K)
    weight_grams = models.DecimalField(max_digits=10, decimal_places=3, help_text="Weight in grams (always positive)")
    balance_after_grams = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            month_str = timezone.now().strftime('%Y%m')
            self.transaction_id = _generate_sequential_id(GoldTransaction, 'transaction_id', f"GLD-{month_str}-", digits=4)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_id}: {self.get_transaction_type_display()} - {self.weight_grams}g ({self.purity})"


# --- STONE INVENTORY & TRANSACTIONS ---
class StoneType(models.TextChoices):
    DIAMOND = 'DIAMOND', 'Natural Diamond'
    LAB_DIAMOND = 'LAB_DIAMOND', 'Lab-Grown Diamond'
    RUBY = 'RUBY', 'Ruby (Manikyam)'
    EMERALD = 'EMERALD', 'Emerald (Panna)'
    SAPPHIRE = 'SAPPHIRE', 'Sapphire (Neelam)'
    CZ_STONE = 'CZ_STONE', 'Cubic Zirconia (CZ)'
    PEARL = 'PEARL', 'Natural / Cultured Pearl'
    POLKI = 'POLKI', 'Uncut Polki Diamond'
    KUNDAN = 'KUNDAN', 'Kundan Glass/Gemstone'
    OTHER = 'OTHER', 'Other Gemstone'

class StoneShape(models.TextChoices):
    ROUND = 'ROUND', 'Round Brilliant'
    PRINCESS = 'PRINCESS', 'Princess Cut'
    OVAL = 'OVAL', 'Oval'
    EMERALD_CUT = 'EMERALD_CUT', 'Emerald Cut'
    MARQUISE = 'MARQUISE', 'Marquise'
    PEAR = 'PEAR', 'Pear Shape'
    CUSHION = 'CUSHION', 'Cushion'
    BAGUETTE = 'BAGUETTE', 'Baguette'
    OTHER = 'OTHER', 'Other Shape'

class Stone(models.Model):
    stone_code = models.CharField(max_length=50, unique=True)
    stone_type = models.CharField(max_length=30, choices=StoneType.choices, default=StoneType.DIAMOND)
    shape = models.CharField(max_length=30, choices=StoneShape.choices, default=StoneShape.ROUND)
    size_mm = models.CharField(max_length=30, blank=True, help_text="e.g. 2.0mm or 0.03ct")
    total_quantity = models.PositiveIntegerField(default=0)
    available_quantity = models.PositiveIntegerField(default=0)
    weight_carats = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'))
    grade = models.CharField(max_length=50, blank=True, help_text="e.g. VVS-EF, AAA, Natural Burma")
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    location = models.CharField(max_length=100, default="Stone Safe Box A")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.stone_code} - {self.get_stone_type_display()} ({self.shape}, {self.size_mm})"


class StoneTransactionType(models.TextChoices):
    ISSUE = 'ISSUE', 'Stone Issued for Job'
    RETURN_UNUSED = 'RETURN_UNUSED', 'Unused Stones Returned'
    RETURN_USED = 'RETURN_USED', 'Fitted into Jewellery'
    DAMAGED = 'DAMAGED', 'Damaged / Chipped during Setting'
    ADJUSTMENT = 'ADJUSTMENT', 'Inventory Adjustment'

class StoneTransaction(models.Model):
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='stone_transactions')
    stone = models.ForeignKey(Stone, on_delete=models.CASCADE, related_name='transactions')
    worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=30, choices=StoneTransactionType.choices)
    quantity = models.PositiveIntegerField(default=1)
    weight_carats = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'))
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.stone.stone_code} - {self.get_transaction_type_display()} ({self.quantity} pcs)"


# --- QUALITY CONTROL (QC) SYSTEM ---
class QCResult(models.TextChoices):
    PASS = 'PASS', 'Pass'
    FAIL = 'FAIL', 'Fail'
    REWORK_REQUIRED = 'REWORK_REQUIRED', 'Rework Required'

class QualityCheck(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='quality_check')
    inspected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    inspection_date = models.DateTimeField(default=timezone.now)
    
    # 10 Point Rigorous Checklist
    design_matches = models.BooleanField(default=False, help_text="Matches customer reference design & sketches")
    correct_weight = models.BooleanField(default=False, help_text="Weight matches specifications within tolerance")
    correct_dimensions = models.BooleanField(default=False, help_text="Ring size, chain length, bangle diameter verified")
    stones_properly_fitted = models.BooleanField(default=False, help_text="Prongs secure, no loose or tilted stones")
    no_visible_scratches = models.BooleanField(default=False, help_text="Surface clean, free of porosity, pitting, scratches")
    polishing_completed = models.BooleanField(default=False, help_text="High mirror gloss / satin finish evenly applied")
    soldering_checked = models.BooleanField(default=False, help_text="Joints clean, no excess solder or weak points")
    locks_hooks_checked = models.BooleanField(default=False, help_text="Clasps, screw backs, hinges smooth and firm")
    finish_checked = models.BooleanField(default=False, help_text="Hallmarking 916/750 clear, rhodium clean")
    final_photo_uploaded = models.BooleanField(default=False, help_text="High-res final photographs uploaded")
    
    result = models.CharField(max_length=20, choices=QCResult.choices, default=QCResult.PASS)
    rework_stage = models.CharField(max_length=50, blank=True, help_text="Stage to send back if rework is needed")
    failure_reason = models.TextField(blank=True, help_text="Mandatory detailed reason if failed or reworked")
    notes = models.TextField(blank=True)

    @property
    def passed_items_count(self):
        checklist = [
            self.design_matches, self.correct_weight, self.correct_dimensions,
            self.stones_properly_fitted, self.no_visible_scratches, self.polishing_completed,
            self.soldering_checked, self.locks_hooks_checked, self.finish_checked,
            self.final_photo_uploaded
        ]
        return sum(1 for item in checklist if item)

    def __str__(self):
        return f"QC for {self.job.job_id}: {self.get_result_display()}"


# --- PAYMENTS & INVOICES ---
class PaymentMethod(models.TextChoices):
    CASH = 'CASH', 'Cash'
    UPI = 'UPI', 'UPI / PhonePe / GPay'
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank IMPS / NEFT'
    CARD = 'CARD', 'Credit / Debit Card'
    CHEQUE = 'CHEQUE', 'Cheque'
    OTHER = 'OTHER', 'Other'

class PaymentType(models.TextChoices):
    ADVANCE = 'ADVANCE', 'Advance Deposit'
    PARTIAL = 'PARTIAL', 'Partial / Stage Payment'
    FINAL = 'FINAL', 'Final Settlement'
    REFUND = 'REFUND', 'Refund'

class Payment(models.Model):
    receipt_number = models.CharField(max_length=40, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.ADVANCE)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.UPI)
    transaction_reference = models.CharField(max_length=100, blank=True, help_text="UPI UTR or Cheque No.")
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateField(default=date.today)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = _generate_sequential_id(Payment, 'receipt_number', 'RCPT-2026-', digits=5)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number}: ₹{self.amount} ({self.customer.name})"


# --- DELIVERIES ---
class Delivery(models.Model):
    delivery_number = models.CharField(max_length=40, unique=True)
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='delivery_record')
    delivered_to_name = models.CharField(max_length=150)
    delivered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    delivery_date = models.DateTimeField(default=timezone.now)
    
    # Pre-delivery Verification Gates
    qc_verified = models.BooleanField(default=True)
    final_weight_verified = models.BooleanField(default=True)
    payment_verified = models.BooleanField(default=True)
    customer_signature_confirmed = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.delivery_number:
            self.delivery_number = _generate_sequential_id(Delivery, 'delivery_number', 'DEL-2026-', digits=5)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.delivery_number} - {self.job.job_id}"


# --- QUOTATIONS ---
class QuotationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    SENT = 'SENT', 'Sent to Customer'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    REJECTED = 'REJECTED', 'Rejected'
    EXPIRED = 'EXPIRED', 'Expired'

class Quotation(models.Model):
    quotation_number = models.CharField(max_length=40, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='quotations')
    jewellery_description = models.TextField()
    gold_estimate_weight = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0.000'))
    gold_rate_per_gram = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('7200.00'))
    stone_estimate_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    making_charges = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    estimated_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT)
    valid_until = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            self.quotation_number = _generate_sequential_id(Quotation, 'quotation_number', 'QUO-2026-', digits=4)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quotation_number} ({self.customer.name})"


# --- EXPENSES ---
class ExpenseCategory(models.TextChoices):
    ELECTRICITY = 'ELECTRICITY', 'Electricity & Power'
    RENT = 'RENT', 'Workshop Rent'
    LABOUR = 'LABOUR', 'Outsourced Labour'
    TOOLS = 'TOOLS', 'Tools, Burrs & Wheels'
    PACKAGING = 'PACKAGING', 'Boxes, Bags & Pouches'
    TRANSPORT = 'TRANSPORT', 'Logistics & Secure Transport'
    MAINTENANCE = 'MAINTENANCE', 'Machine Maintenance'
    CHEMICALS = 'CHEMICALS', 'Acids, Flux & Polishing Rouge'
    OTHER = 'OTHER', 'Other Expense'

class Expense(models.Model):
    title = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices, default=ExpenseCategory.TOOLS)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=date.today)
    description = models.TextField(blank=True)
    receipt_image = models.ImageField(upload_to='expenses/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title}: ₹{self.amount} ({self.date})"


# --- NOTIFICATIONS & AUDIT LOG ---
class NotificationType(models.TextChoices):
    DELAYED = 'DELAYED', 'Job Delayed'
    DUE_TODAY = 'DUE_TODAY', 'Job Due Today'
    COMPLETED = 'COMPLETED', 'Job Completed'
    MATERIAL_WAITING = 'MATERIAL_WAITING', 'Material Waiting'
    QC_PENDING = 'QC_PENDING', 'QC Pending'
    PAYMENT_PENDING = 'PAYMENT_PENDING', 'Payment Pending'
    READY_DELIVERY = 'READY_DELIVERY', 'Ready for Delivery'

class Notification(models.Model):
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=150)
    message = models.TextField()
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title}"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp.strftime('%d/%m/%Y %H:%M')} - {self.user}: {self.action} on {self.object_repr}"


# --- BACKUP RECORDS ---
class BackupRecord(models.Model):
    backup_file = models.CharField(max_length=255)
    backup_type = models.CharField(max_length=50, default="FULL_ARCHIVE")
    file_size_bytes = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, default="SUCCESS")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def file_size_display(self):
        size_kb = self.file_size_bytes / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        return f"{(size_kb / 1024):.2f} MB"

    def __str__(self):
        return f"Backup {self.backup_file} ({self.status}) at {self.created_at.strftime('%d/%m/%Y %H:%M')}"


# --- LIVE BULLION MARKET RATES (CHENNAI & BANGALORE) ---
class DailyMarketRate(models.Model):
    CITY_CHOICES = [
        ('CHENNAI', 'Chennai'),
        ('BANGALORE', 'Bangalore'),
    ]
    city = models.CharField(max_length=20, choices=CITY_CHOICES, default='CHENNAI')
    gold_24k_per_gram = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('7480.00'), help_text="₹/gram 24K (999 pure)")
    gold_22k_per_gram = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('6860.00'), help_text="₹/gram 22K (916 hallmark)")
    gold_18k_per_gram = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('5610.00'), help_text="₹/gram 18K (750 hallmark)")
    silver_per_gram = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('94.50'), help_text="₹/gram fine silver")
    silver_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('94500.00'), help_text="₹/kg bar silver")
    rate_date = models.DateField(default=date.today)
    change_24k_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('25.00'), help_text="Daily price change in ₹")
    change_24k_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.33'), help_text="Daily price change in %")
    change_direction = models.CharField(max_length=10, default='UP') # 'UP', 'DOWN', 'FLAT'
    is_live = models.BooleanField(default=True)
    source = models.CharField(max_length=100, default="IBJA / Bullion Direct Spot")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['city', '-rate_date', '-updated_at']
        verbose_name = "Daily Market Rate"
        verbose_name_plural = "Daily Market Rates"

    def __str__(self):
        return f"[{self.get_city_display()}] {self.rate_date}: 24K Rs.{self.gold_24k_per_gram}, 22K Rs.{self.gold_22k_per_gram}, Ag Rs.{self.silver_per_gram}/g"
