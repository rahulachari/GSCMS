import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as PDFImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import (
    WorkshopSettings, UserProfile, UserRole, Worker, WorkerSkill,
    Customer, CustomerNote, Order, OrderType, PriorityLevel, OrderStatus,
    Job, JewelleryType, GoldPurity, JobOverallStatus, PhysicalLocation,
    StageCode, JobStageHistory, StageStatus, JobPhoto, PhotoCategory,
    GoldTransaction, GoldTransactionType, Stone, StoneTransaction, StoneTransactionType,
    QualityCheck, QCResult, Payment, PaymentMethod, PaymentType, Delivery, Expense,
    Notification, NotificationType, AuditLog, BackupRecord, DailyMarketRate
)
import json
import base64
import io
import qrcode
from .rates_service import get_or_seed_rates, BENCHMARK_RATES
from .services import (
    log_audit, export_jobs_to_excel, export_gold_ledger_to_excel,
    create_complete_job_zip, perform_system_backup
)


# --- AUTHENTICATION & LOGIN (BYPASSED - DIRECT ACCESS) ---
def login_view(request):
    return redirect('dashboard')

def logout_view(request):
    return redirect('dashboard')



# --- MAIN DASHBOARD & OWNER DAILY SUMMARY ---
@login_required
def dashboard_view(request):
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()
    now = timezone.now()

    # Owner KPI Metrics (Excluding Soft Deleted)
    new_orders_today = Order.objects.filter(is_deleted=False, created_at__date=today).count()
    total_customers = Customer.objects.filter(is_deleted=False).count()
    active_jobs = Job.objects.filter(is_deleted=False, overall_status__in=['ASSIGNED', 'IN_PROGRESS', 'WAITING', 'QC_PENDING']).count()
    completed_today = Job.objects.filter(is_deleted=False, overall_status__in=['READY', 'DELIVERED'], completion_date__date=today).count()
    ready_for_delivery = Job.objects.filter(is_deleted=False, overall_status='READY').count()
    
    # Delayed Jobs
    all_active_jobs = Job.objects.filter(is_deleted=False, overall_status__in=['ASSIGNED', 'IN_PROGRESS', 'WAITING', 'QC_PENDING']).select_related('order', 'order__customer', 'current_worker')
    delayed_jobs = [j for j in all_active_jobs if j.is_delayed]
    delayed_count = len(delayed_jobs)

    # Financial Dues
    total_active_orders = Order.objects.filter(is_deleted=False, status__in=['PENDING', 'IN_PROGRESS'])
    total_estimated = sum(o.total_estimated_amount for o in total_active_orders) or Decimal('0.00')
    total_advance = sum(o.advance_paid for o in total_active_orders) or Decimal('0.00')
    payments_due = max(Decimal('0.00'), total_estimated - total_advance)

    # Kanban Columns Configuration (Excluding Deleted)
    kanban_columns = [
        {
            'key': 'PENDING',
            'title': 'Pending Assignment',
            'color': '#86868b',
            'jobs': Job.objects.filter(is_deleted=False, overall_status='PENDING').select_related('order', 'order__customer', 'current_worker')
        },
        {
            'key': 'MAKING',
            'title': 'Making & Handcrafting',
            'color': '#0071e3',
            'jobs': Job.objects.filter(is_deleted=False, current_stage__in=[StageCode.MELTING, StageCode.CASTING, StageCode.MAKING, StageCode.FILING, StageCode.SOLDERING], overall_status='IN_PROGRESS').select_related('order', 'order__customer', 'current_worker')
        },
        {
            'key': 'STONE_SETTING',
            'title': 'Stone Setting',
            'color': '#af52de',
            'jobs': Job.objects.filter(is_deleted=False, current_stage=StageCode.STONE_SETTING, overall_status='IN_PROGRESS').select_related('order', 'order__customer', 'current_worker')
        },
        {
            'key': 'POLISHING',
            'title': 'Polishing & Finish',
            'color': '#ff9500',
            'jobs': Job.objects.filter(is_deleted=False, current_stage__in=[StageCode.POLISHING, StageCode.FINISHING], overall_status='IN_PROGRESS').select_related('order', 'order__customer', 'current_worker')
        },
        {
            'key': 'QC',
            'title': 'Quality Check (QC)',
            'color': '#5856d6',
            'jobs': Job.objects.filter(is_deleted=False, overall_status='QC_PENDING').select_related('order', 'order__customer', 'current_worker')
        },
        {
            'key': 'READY',
            'title': 'Ready for Delivery',
            'color': '#34c759',
            'jobs': Job.objects.filter(is_deleted=False, overall_status='READY').select_related('order', 'order__customer', 'current_worker')
        },
    ]

    # Attention Required (Delayed, Due Today, Waiting for Material/Customer)
    due_today_jobs = Job.objects.filter(is_deleted=False, overall_status__in=['ASSIGNED', 'IN_PROGRESS'], target_date__date=today).exclude(id__in=[j.id for j in delayed_jobs])
    waiting_jobs = Job.objects.filter(is_deleted=False, overall_status='WAITING')

    # Visual Graph Data (Simple, understandable at a single glance)
    # 1. 7-Day Gold & Silver Trend
    trend_labels = []
    gold_24k_trend = []
    gold_22k_trend = []
    silver_trend = []
    base_24k = 7480
    base_22k = 6860
    base_silver = 94.50
    offsets = [-60, -45, -30, -50, -20, -10, 0]
    silver_offsets = [-1.5, -1.2, -0.8, -1.0, -0.5, -0.2, 0]
    
    for i in range(7):
        d = today - timedelta(days=6-i)
        trend_labels.append(d.strftime('%d %b'))
        gold_24k_trend.append(base_24k + offsets[i])
        gold_22k_trend.append(base_22k + int(offsets[i] * 0.916))
        silver_trend.append(round(base_silver + silver_offsets[i], 2))

    # 2. Workshop Stage Distribution for Graph
    stage_counts = [
        Job.objects.filter(is_deleted=False, overall_status='PENDING').count(),
        Job.objects.filter(is_deleted=False, current_stage__in=[StageCode.MELTING, StageCode.CASTING, StageCode.MAKING, StageCode.FILING, StageCode.SOLDERING], overall_status='IN_PROGRESS').count(),
        Job.objects.filter(is_deleted=False, current_stage=StageCode.STONE_SETTING, overall_status='IN_PROGRESS').count(),
        Job.objects.filter(is_deleted=False, current_stage__in=[StageCode.POLISHING, StageCode.FINISHING], overall_status='IN_PROGRESS').count(),
        Job.objects.filter(is_deleted=False, overall_status='QC_PENDING').count(),
        Job.objects.filter(is_deleted=False, overall_status='READY').count(),
    ]

    context = {
        'new_orders_today': new_orders_today,
        'active_jobs_count': active_jobs,
        'completed_today_count': completed_today,
        'total_customers': total_customers,
        'delayed_jobs_count': delayed_count,
        'ready_for_delivery_count': ready_for_delivery,
        'payments_due_total': payments_due,
        'delayed_jobs': delayed_jobs[:5],
        'due_today_jobs': due_today_jobs[:5],
        'waiting_jobs': waiting_jobs[:5],
        'kanban_columns': kanban_columns,
        'trend_labels_json': json.dumps(trend_labels),
        'gold_24k_trend_json': gold_24k_trend,
        'gold_22k_trend_json': gold_22k_trend,
        'silver_trend_json': silver_trend,
        'stage_counts_json': json.dumps(stage_counts),
    }
    return render(request, 'workshop/dashboard.html', context)


# --- CUSTOMER MANAGEMENT ---
@login_required
def customer_list(request):
    query = request.GET.get('q', '').strip()
    customers = Customer.objects.filter(is_deleted=False).order_by('-created_at')
    if query:
        customers = customers.filter(
            Q(name__icontains=query) | Q(mobile__icontains=query) | Q(customer_id__icontains=query)
        )
    return render(request, 'workshop/customers/list.html', {'customers': customers, 'query': query})

@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if customer.is_deleted:
        messages.warning(request, f"Note: Customer {customer.name} is in the Recycle Bin.")
    orders = customer.orders.filter(is_deleted=False).order_by('-created_at')
    notes = customer.customer_notes.all().order_by('-created_at')
    payments = customer.payments.all().order_by('-created_at')

    if request.method == 'POST' and 'add_note' in request.POST:
        note_text = request.POST.get('note', '').strip()
        if note_text:
            CustomerNote.objects.create(customer=customer, author=request.user, note=note_text)
            messages.success(request, "Customer note recorded.")
            return redirect('customer_detail', pk=pk)

    context = {
        'customer': customer,
        'orders': orders,
        'notes': notes,
        'payments': payments,
    }
    return render(request, 'workshop/customers/detail.html', context)

@login_required
def customer_create(request):
    jewellery_types = JewelleryType.choices
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        mobile = request.POST.get('mobile', '').strip()
        alternate_mobile = request.POST.get('alternate_mobile', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not name or not mobile:
            messages.error(request, "Customer name and mobile number are required.")
            return render(request, 'workshop/customers/form.html', {'jewellery_types': jewellery_types})

        j_type = request.POST.get('jewellery_type', '')
        custom_name = request.POST.get('custom_type_name', '').strip()
        purity = request.POST.get('gold_purity', GoldPurity.P_22K)
        requirements = request.POST.get('requirements', '').strip()
        weight_str = request.POST.get('expected_weight', '').strip()
        if j_type not in dict(jewellery_types):
            messages.error(request, "Choose a jewellery item type from the list.")
            return render(request, 'workshop/customers/form.html', {'jewellery_types': jewellery_types})
        if j_type == JewelleryType.OTHER and not custom_name:
            messages.error(request, "Enter the custom jewellery item name.")
            return render(request, 'workshop/customers/form.html', {'jewellery_types': jewellery_types})
        if purity not in dict(GoldPurity.choices):
            messages.error(request, "Choose a valid gold purity.")
            return render(request, 'workshop/customers/form.html', {'jewellery_types': jewellery_types})
        try:
            weight = Decimal(weight_str)
            if (not weight.is_finite() or weight < 0 or weight > Decimal('99999.999')
                    or weight.quantize(Decimal('0.001')) != weight):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid expected weight in grams (zero or greater, up to three decimals).")
            return render(request, 'workshop/customers/form.html', {'jewellery_types': jewellery_types})

        cust = Customer.objects.create(
            name=name, mobile=mobile, alternate_mobile=alternate_mobile,
            email=email, address=address, notes=notes
        )
        log_audit(request.user, "Created Customer", cust, f"Customer: {name}", request)

        # Optional Item Intake right on customer creation
        if j_type:
            type_label = dict(jewellery_types)[j_type]
            title = custom_name if (j_type == JewelleryType.OTHER and custom_name) else f"{purity} {type_label}"

            order = Order.objects.create(
                customer=cust,
                order_type=OrderType.NEW_JEWELLERY,
                priority=PriorityLevel.NORMAL,
                customer_instructions=requirements,
                status=OrderStatus.IN_PROGRESS
            )

            job = Job.objects.create(
                order=order,
                jewellery_type=j_type,
                custom_type_name=custom_name,
                title=title,
                gold_purity=purity,
                expected_weight=weight,
                special_instructions=requirements,
                atelier_stage='RECEIVED',
                current_stage=StageCode.ORDER_RECEIVED,
                overall_status=JobOverallStatus.IN_PROGRESS
            )

            # Handle Reference Image Upload
            if 'reference_photo' in request.FILES:
                JobPhoto.objects.create(
                    job=job,
                    image=request.FILES['reference_photo'],
                    category=PhotoCategory.CUSTOMER_REF,
                    caption=f"Reference picture for {title}",
                    uploaded_by=request.user if request.user.is_authenticated else None
                )

        messages.success(request, f"Customer {name} registered with work item.")
        return redirect('customer_detail', pk=cust.pk)

    return render(request, 'workshop/customers/form.html', {'jewellery_types': jewellery_types})

@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.name = request.POST.get('name', customer.name)
        customer.mobile = request.POST.get('mobile', customer.mobile)
        customer.alternate_mobile = request.POST.get('alternate_mobile', customer.alternate_mobile)
        customer.email = request.POST.get('email', customer.email)
        customer.address = request.POST.get('address', customer.address)
        customer.notes = request.POST.get('notes', customer.notes)
        customer.save()

        log_audit(request.user, "Updated Customer", customer, f"Updated: {customer.name}", request)
        messages.success(request, f"Customer {customer.name} updated successfully.")
        
        # Check if ajax
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'name': customer.name, 'mobile': customer.mobile})
        
        return redirect('customer_detail', pk=customer.pk)
    
    return render(request, 'workshop/customers/edit.html', {'customer': customer})


# --- ORDER CREATION & ITEM SPLITTING ---
@login_required
def order_list(request):
    status_filter = request.GET.get('status')
    query = request.GET.get('q', '').strip()
    orders = Order.objects.filter(is_deleted=False).select_related('customer').order_by('-created_at')

    if status_filter:
        orders = orders.filter(status=status_filter)
    if query:
        orders = orders.filter(
            Q(order_number__icontains=query) | Q(customer__name__icontains=query) | Q(customer__mobile__icontains=query)
        )

    return render(request, 'workshop/orders/list.html', {'orders': orders, 'query': query, 'status_filter': status_filter})

@login_required
def order_create(request):
    customers = Customer.objects.all().order_by('name')
    workers = Worker.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        customer_choice = request.POST.get('customer_choice') # 'existing' or 'new'
        if customer_choice == 'new':
            c_name = request.POST.get('new_customer_name')
            c_mobile = request.POST.get('new_customer_mobile')
            c_email = request.POST.get('new_customer_email', '')
            c_addr = request.POST.get('new_customer_address', '')
            customer = Customer.objects.create(name=c_name, mobile=c_mobile, email=c_email, address=c_addr)
        else:
            cust_id = request.POST.get('customer_id')
            customer = get_object_or_404(Customer, pk=cust_id)

        order_type = request.POST.get('order_type', OrderType.NEW_JEWELLERY)
        priority = request.POST.get('priority', PriorityLevel.NORMAL)
        delivery_date = request.POST.get('required_delivery_date') or None
        instructions = request.POST.get('customer_instructions', '')
        internal_notes = request.POST.get('internal_notes', '')
        est_amount = Decimal(request.POST.get('total_estimated_amount', '0.00') or '0.00')
        advance = Decimal(request.POST.get('advance_paid', '0.00') or '0.00')
        payment_method = request.POST.get('payment_method', PaymentMethod.UPI)
        payment_ref = request.POST.get('payment_reference', '')

        # Create Order
        order = Order.objects.create(
            customer=customer,
            order_type=order_type,
            priority=priority,
            required_delivery_date=delivery_date,
            customer_instructions=instructions,
            internal_notes=internal_notes,
            total_estimated_amount=est_amount,
            advance_paid=advance,
            status=OrderStatus.IN_PROGRESS if advance > 0 else OrderStatus.PENDING
        )

        # Record Advance Payment if received
        if advance > 0:
            Payment.objects.create(
                order=order,
                customer=customer,
                amount=advance,
                payment_type=PaymentType.ADVANCE,
                payment_method=payment_method,
                transaction_reference=payment_ref,
                received_by=request.user,
                notes=f"Advance deposit for {order.order_number}"
            )

        # Create Split Jobs from item rows
        item_types = request.POST.getlist('item_type[]')
        item_titles = request.POST.getlist('item_title[]')
        item_purities = request.POST.getlist('item_purity[]')
        item_weights = request.POST.getlist('item_expected_weight[]')
        item_workers = request.POST.getlist('item_worker[]')

        for idx in range(len(item_types)):
            j_type = item_types[idx]
            j_title = item_titles[idx] or f"{j_type.title()} Piece"
            j_purity = item_purities[idx]
            j_weight = Decimal(item_weights[idx] or '0.000')
            w_id = item_workers[idx] if idx < len(item_workers) and item_workers[idx] else None
            worker = Worker.objects.filter(pk=w_id).first() if w_id else None

            job = Job.objects.create(
                order=order,
                jewellery_type=j_type,
                title=j_title,
                gold_purity=j_purity,
                expected_weight=j_weight,
                current_worker=worker,
                current_stage=StageCode.MAKING if worker else StageCode.ORDER_RECEIVED,
                overall_status=JobOverallStatus.IN_PROGRESS if worker else JobOverallStatus.PENDING,
                target_date=datetime.combine(datetime.strptime(delivery_date, "%Y-%m-%d").date(), datetime.min.time()) if delivery_date else None,
                start_date=timezone.now() if worker else None
            )

            # Record initial stage history
            JobStageHistory.objects.create(
                job=job,
                stage_name=job.current_stage,
                worker=worker,
                assigned_by=request.user,
                status=StageStatus.IN_PROGRESS if worker else StageStatus.PENDING,
                start_time=timezone.now() if worker else None
            )

        # Handle Reference Photo upload if provided
        ref_photo = request.FILES.get('reference_image')
        if ref_photo and order.jobs.exists():
            first_job = order.jobs.first()
            JobPhoto.objects.create(
                job=first_job,
                category=PhotoCategory.REFERENCE_SKETCH,
                image=ref_photo,
                caption="Customer Reference Design at Order Booking",
                uploaded_by=request.user
            )

        log_audit(request.user, "Created Order", order, f"{order.order_number} for {customer.name}", request)
        messages.success(request, f"Order {order.order_number} created with {order.jobs.count()} jewellery jobs.")
        return redirect('order_detail', pk=order.pk)

    return render(request, 'workshop/orders/form.html', {'customers': customers, 'workers': workers})

@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('customer'), pk=pk)
    jobs = order.jobs.all().select_related('current_worker').prefetch_related('photos')
    payments = order.payments.all().order_by('-created_at')
    return render(request, 'workshop/orders/detail.html', {'order': order, 'jobs': jobs, 'payments': payments})


# --- JOB DETAIL & PRODUCTION HUB ---
@login_required
def job_list(request):
    stage_filter = request.GET.get('stage')
    worker_filter = request.GET.get('worker')
    purity_filter = request.GET.get('purity')
    delayed_only = request.GET.get('delayed') == '1'
    query = request.GET.get('q', '').strip()

    jobs = Job.objects.filter(is_deleted=False).select_related('order', 'order__customer', 'current_worker').order_by('-created_at')

    if stage_filter:
        jobs = jobs.filter(current_stage=stage_filter)
    if worker_filter:
        jobs = jobs.filter(current_worker_id=worker_filter)
    if purity_filter:
        jobs = jobs.filter(gold_purity=purity_filter)
    if query:
        jobs = jobs.filter(
            Q(job_id__icontains=query) | Q(title__icontains=query) | Q(order__customer__name__icontains=query) | Q(order__order_number__icontains=query)
        )

    if delayed_only:
        jobs = [j for j in jobs if j.is_delayed]

    workers = Worker.objects.filter(is_active=True).order_by('name')
    return render(request, 'workshop/jobs/list.html', {
        'jobs': jobs, 'workers': workers, 'stage_filter': stage_filter,
        'worker_filter': worker_filter, 'purity_filter': purity_filter,
        'delayed_only': delayed_only, 'query': query
    })

@login_required
def job_detail(request, job_id):
    job = get_object_or_404(
        Job.objects.select_related('order', 'order__customer', 'current_worker'),
        job_id=job_id
    )
    _refresh_job_qr(job, request)
    photos = job.photos.all().order_by('-created_at')
    ref_photos = photos.filter(category__in=['REFERENCE_FRONT', 'REFERENCE_SIDE', 'REFERENCE_BACK', 'REFERENCE_SKETCH', 'CUSTOMER_REF'])
    final_photos = photos.filter(category__in=['FINAL_FRONT', 'FINAL_SIDE', 'FINAL_BACK', 'FINAL_CLOSEUP', 'STONE_DETAIL', 'PACKAGING'])
    progress_photos = photos.filter(category='PROGRESS')

    stage_histories = job.stage_histories.all().select_related('worker')
    gold_txns = job.gold_transactions.all().select_related('worker', 'created_by')
    stone_txns = job.stone_transactions.all().select_related('stone', 'worker')
    all_workers = Worker.objects.filter(is_active=True)

    # Handle Photo Upload
    if request.method == 'POST' and 'upload_photo' in request.POST:
        category = request.POST.get('photo_category', PhotoCategory.PROGRESS)
        caption = request.POST.get('caption', '')
        img_file = request.FILES.get('photo_file')
        if img_file:
            try:
                user = request.user if request.user.is_authenticated else None
                jp = JobPhoto.objects.create(
                    job=job,
                    category=category,
                    image=img_file,
                    caption=caption,
                    uploaded_by=user,
                    worker=job.current_worker
                )
                if 'FINAL' in str(category):
                    qc = getattr(job, 'quality_check', None)
                    if qc:
                        qc.final_photo_uploaded = True
                        qc.save()
                log_audit(user, "Uploaded Job Photo", job, f"Category: {category}", request)
                messages.success(request, "Photograph uploaded successfully.")
            except Exception as e:
                messages.error(request, f"Error saving photograph: {e}")
            return redirect('job_detail', job_id=job.job_id)

    # Handle Final Weight Recording
    if request.method == 'POST' and 'record_final_weight' in request.POST:
        gross_wt = Decimal(request.POST.get('final_gross_weight', '0.000'))
        net_wt = Decimal(request.POST.get('net_gold_weight', '0.000'))
        st_wt = Decimal(request.POST.get('stone_weight', '0.000'))
        wastage_wt = Decimal(request.POST.get('wastage_weight', '0.000'))

        job.final_gross_weight = gross_wt
        job.net_gold_weight = net_wt
        job.stone_weight = st_wt
        job.wastage_weight = wastage_wt
        job.save()

        log_audit(request.user, "Recorded Final Weight", job, f"Gross: {gross_wt}g, Net Gold: {net_wt}g", request)
        messages.success(request, f"Final weight recorded: Gross {gross_wt}g, Net {net_wt}g.")
        return redirect('job_detail', job_id=job.job_id)

    # Handle Customer Design Approval
    if request.method == 'POST' and 'mark_approved' in request.POST:
        job.customer_approved = True
        job.approved_at = timezone.now()
        job.approved_by = request.POST.get('approved_by', 'Customer via Workshop')
        job.save()
        log_audit(request.user, "Design Approved", job, f"Approved by {job.approved_by}", request)
        messages.success(request, "Customer design approval recorded.")
        return redirect('job_detail', job_id=job.job_id)

    context = {
        'job': job,
        'ref_photos': ref_photos,
        'final_photos': final_photos,
        'progress_photos': progress_photos,
        'stage_histories': stage_histories,
        'gold_txns': gold_txns,
        'stone_txns': stone_txns,
        'all_workers': all_workers,
        'stage_choices': StageCode.choices,
    }
    return render(request, 'workshop/jobs/detail.html', context)


def _refresh_job_qr(job, request):
    """Keep stored job QR images as absolute, camera-openable dossier links."""
    if job.qr_code_image:
        job.qr_code_image.delete(save=False)
    job.generate_qr(base_url=request.build_absolute_uri('/').rstrip('/'))
    job.save(update_fields=['qr_code_image'])

@login_required
def job_card_print(request, job_id):
    job = get_object_or_404(Job.objects.select_related('order', 'order__customer', 'current_worker'), job_id=job_id)
    _refresh_job_qr(job, request)
    return render(request, 'workshop/jobs/card_print.html', {'job': job})

@login_required
def job_comparison_view(request, job_id):
    job = get_object_or_404(Job, job_id=job_id)
    ref_photo = job.photos.filter(category__in=['REFERENCE_FRONT', 'REFERENCE_SKETCH', 'CUSTOMER_REF']).first()
    final_photo = job.photos.filter(category__in=['FINAL_FRONT', 'FINAL_SIDE', 'FINAL_CLOSEUP']).first()
    return render(request, 'workshop/jobs/comparison.html', {'job': job, 'ref_photo': ref_photo, 'final_photo': final_photo})

@login_required
def job_export_zip(request, job_id):
    job = get_object_or_404(Job, job_id=job_id)
    zip_buffer = create_complete_job_zip(job)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="Job_Dossier_{job.job_id}.zip"'
    return response


# --- WORKER ROSTER & TOUCH STATION ---
@login_required
def worker_list(request):
    workers = Worker.objects.all().order_by('name')
    return render(request, 'workshop/workers/list.html', {'workers': workers})

@login_required
def worker_station(request, worker_id=None):
    """Touch-optimized Karigar station for workshop phones and tablets"""
    workers = Worker.objects.filter(is_active=True)
    selected_worker = None
    if worker_id:
        selected_worker = get_object_or_404(Worker, worker_id=worker_id)
    elif workers.exists():
        selected_worker = workers.first()

    assigned_jobs = []
    if selected_worker:
        assigned_jobs = selected_worker.assigned_jobs.filter(
            overall_status__in=['ASSIGNED', 'IN_PROGRESS', 'WAITING']
        ).select_related('order', 'order__customer')

    context = {
        'workers': workers,
        'selected_worker': selected_worker,
        'assigned_jobs': assigned_jobs,
    }
    return render(request, 'workshop/workers/station.html', context)


# --- GOLD MANAGEMENT & IMMUTABLE LEDGER ---
@login_required
def gold_ledger_view(request):
    transactions = GoldTransaction.objects.all().select_related('job', 'worker', 'created_by').order_by('-created_at')
    
    # Calculate current balances
    total_issued = sum(t.weight_grams for t in transactions if t.transaction_type == GoldTransactionType.GOLD_ISSUED) or Decimal('0.000')
    total_returned = sum(t.weight_grams for t in transactions if t.transaction_type in [GoldTransactionType.FINISHED_RETURNED, GoldTransactionType.SCRAP_RETURNED, GoldTransactionType.DUST_RECOVERED]) or Decimal('0.000')
    net_in_circulation = total_issued - total_returned

    workers = Worker.objects.filter(is_active=True)
    jobs = Job.objects.filter(overall_status__in=['ASSIGNED', 'IN_PROGRESS'])

    if request.method == 'POST' and 'issue_gold' in request.POST:
        job_id_str = request.POST.get('job_id')
        worker_id_str = request.POST.get('worker_id')
        purity = request.POST.get('purity', GoldPurity.P_22K)
        wt = Decimal(request.POST.get('weight_grams', '0.000'))
        notes = request.POST.get('notes', '')

        job_obj = Job.objects.filter(job_id=job_id_str).first() if job_id_str else None
        worker_obj = Worker.objects.filter(pk=worker_id_str).first() if worker_id_str else None

        txn = GoldTransaction.objects.create(
            job=job_obj,
            worker=worker_obj,
            transaction_type=GoldTransactionType.GOLD_ISSUED,
            purity=purity,
            weight_grams=wt,
            notes=notes,
            created_by=request.user
        )
        log_audit(request.user, "Issued Gold", txn, f"{wt}g {purity} to {worker_obj}", request)
        messages.success(request, f"Issued {wt}g ({purity}) to {worker_obj.name}.")
        return redirect('gold_ledger')

    if request.method == 'POST' and 'return_gold' in request.POST:
        job_id_str = request.POST.get('job_id')
        worker_id_str = request.POST.get('worker_id')
        txn_type = request.POST.get('transaction_type', GoldTransactionType.FINISHED_RETURNED)
        purity = request.POST.get('purity', GoldPurity.P_22K)
        wt = Decimal(request.POST.get('weight_grams', '0.000'))
        notes = request.POST.get('notes', '')

        job_obj = Job.objects.filter(job_id=job_id_str).first() if job_id_str else None
        worker_obj = Worker.objects.filter(pk=worker_id_str).first() if worker_id_str else None

        txn = GoldTransaction.objects.create(
            job=job_obj,
            worker=worker_obj,
            transaction_type=txn_type,
            purity=purity,
            weight_grams=wt,
            notes=notes,
            created_by=request.user
        )
        log_audit(request.user, "Returned Gold", txn, f"{txn.get_transaction_type_display()}: {wt}g", request)
        messages.success(request, f"Recorded {txn.get_transaction_type_display()} of {wt}g.")
        return redirect('gold_ledger')

    context = {
        'transactions': transactions,
        'total_issued': total_issued,
        'total_returned': total_returned,
        'net_in_circulation': net_in_circulation,
        'workers': workers,
        'jobs': jobs,
        'purity_choices': GoldPurity.choices,
        'return_types': [
            (GoldTransactionType.FINISHED_RETURNED, 'Finished Item Gold Returned'),
            (GoldTransactionType.SCRAP_RETURNED, 'Scrap Gold Returned'),
            (GoldTransactionType.DUST_RECOVERED, 'Polishing Dust / Vacuum Recovered'),
            (GoldTransactionType.MELTING_LOSS, 'Melting / Fire Loss'),
        ]
    }
    return render(request, 'workshop/gold/ledger.html', context)


# --- STONE INVENTORY & ISSUE ---
@login_required
def stone_inventory_view(request):
    stones = Stone.objects.all().order_by('stone_code')
    transactions = StoneTransaction.objects.all().select_related('stone', 'job', 'worker').order_by('-created_at')[:20]

    if request.method == 'POST' and 'issue_stone' in request.POST:
        stone_id = request.POST.get('stone_id')
        job_id_str = request.POST.get('job_id')
        worker_id_str = request.POST.get('worker_id')
        qty = int(request.POST.get('quantity', 1))
        wt = Decimal(request.POST.get('weight_carats', '0.000'))
        notes = request.POST.get('notes', '')

        st_obj = get_object_or_404(Stone, pk=stone_id)
        job_obj = Job.objects.filter(job_id=job_id_str).first()
        worker_obj = Worker.objects.filter(pk=worker_id_str).first()

        if st_obj.available_quantity >= qty:
            st_obj.available_quantity -= qty
            st_obj.save()

            st_txn = StoneTransaction.objects.create(
                job=job_obj,
                stone=st_obj,
                worker=worker_obj,
                transaction_type=StoneTransactionType.ISSUE,
                quantity=qty,
                weight_carats=wt,
                notes=notes,
                created_by=request.user
            )
            log_audit(request.user, "Issued Stones", st_txn, f"{qty} pcs to {worker_obj}", request)
            messages.success(request, f"Issued {qty} pcs of {st_obj.stone_code}.")
        else:
            messages.error(request, f"Insufficient stock. Available: {st_obj.available_quantity}")
        return redirect('stone_inventory')

    jobs = Job.objects.filter(overall_status__in=['ASSIGNED', 'IN_PROGRESS'])
    workers = Worker.objects.filter(is_active=True)

    return render(request, 'workshop/stones/inventory.html', {
        'stones': stones, 'transactions': transactions, 'jobs': jobs, 'workers': workers
    })


# --- QUALITY CONTROL (QC) INSPECTION ---
@login_required
def qc_desk_view(request):
    qc_jobs = Job.objects.filter(
        Q(overall_status='QC_PENDING') | Q(current_stage=StageCode.QUALITY_CHECK)
    ).select_related('order', 'order__customer', 'current_worker')
    return render(request, 'workshop/qc/list.html', {'qc_jobs': qc_jobs})

@login_required
def qc_inspect_job(request, job_id):
    job = get_object_or_404(Job.objects.select_related('order', 'order__customer'), job_id=job_id)
    qc_record, _ = QualityCheck.objects.get_or_create(job=job)

    if request.method == 'POST':
        # 10 Point Rigorous Checklist items
        qc_record.design_matches = 'chk_design' in request.POST
        qc_record.correct_weight = 'chk_weight' in request.POST
        qc_record.correct_dimensions = 'chk_dimensions' in request.POST
        qc_record.stones_properly_fitted = 'chk_stones' in request.POST
        qc_record.no_visible_scratches = 'chk_scratches' in request.POST
        qc_record.polishing_completed = 'chk_polish' in request.POST
        qc_record.soldering_checked = 'chk_solder' in request.POST
        qc_record.locks_hooks_checked = 'chk_locks' in request.POST
        qc_record.finish_checked = 'chk_finish' in request.POST
        qc_record.final_photo_uploaded = 'chk_photo' in request.POST
        
        result = request.POST.get('result', QCResult.PASS)
        failure_reason = request.POST.get('failure_reason', '').strip()
        rework_stage = request.POST.get('rework_stage', '')

        qc_record.result = result
        qc_record.failure_reason = failure_reason
        qc_record.rework_stage = rework_stage
        qc_record.inspected_by = request.user
        qc_record.save()

        if result == QCResult.PASS:
            job.overall_status = JobOverallStatus.READY
            job.current_stage = StageCode.READY
            job.current_location = PhysicalLocation.READY_DISPLAY
            job.completion_date = timezone.now()
            job.save()

            Notification.objects.create(
                notification_type=NotificationType.READY_DELIVERY,
                title=f"Ready for Delivery: {job.job_id}",
                message=f"{job.title} passed Quality Control and is ready for customer delivery.",
                job=job
            )
            messages.success(request, f"QC PASSED! Job {job.job_id} moved to Ready for Delivery.")
        else: # REWORK REQUIRED
            if not failure_reason:
                messages.error(request, "Mandatory detailed failure reason required for rework.")
                return redirect('qc_inspect', job_id=job.job_id)

            # Route back to rework stage
            job.current_stage = rework_stage or StageCode.MAKING
            job.overall_status = JobOverallStatus.IN_PROGRESS
            job.save()

            # Record rework stage history
            JobStageHistory.objects.create(
                job=job,
                stage_name=job.current_stage,
                worker=job.current_worker,
                assigned_by=request.user,
                status=StageStatus.REWORK_REQUIRED,
                is_rework=True,
                rework_reason=failure_reason
            )
            messages.warning(request, f"Job {job.job_id} routed back to {job.get_current_stage_display()} for rework.")

        log_audit(request.user, f"QC Inspection {result}", job, f"Passed {qc_record.passed_items_count}/10. {failure_reason}", request)
        return redirect('qc_desk')

    return render(request, 'workshop/qc/inspect.html', {'job': job, 'qc': qc_record, 'stages': StageCode.choices})


# --- PAYMENTS & INVOICES ---
@login_required
def payment_list_view(request):
    payments = Payment.objects.all().select_related('order', 'customer', 'received_by').order_by('-created_at')
    orders = Order.objects.filter(status__in=[OrderStatus.PENDING, OrderStatus.IN_PROGRESS]).select_related('customer')

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        amt = Decimal(request.POST.get('amount', '0.00'))
        ptype = request.POST.get('payment_type', PaymentType.PARTIAL)
        pmethod = request.POST.get('payment_method', PaymentMethod.UPI)
        ref = request.POST.get('transaction_reference', '')
        notes = request.POST.get('notes', '')

        order_obj = get_object_or_404(Order, pk=order_id)
        payment = Payment.objects.create(
            order=order_obj,
            customer=order_obj.customer,
            amount=amt,
            payment_type=ptype,
            payment_method=pmethod,
            transaction_reference=ref,
            received_by=request.user,
            notes=notes
        )
        # Update order amounts
        order_obj.advance_paid += amt
        order_obj.save()

        log_audit(request.user, "Recorded Payment", payment, f"₹{amt} via {pmethod}", request)
        messages.success(request, f"Payment of ₹{amt} recorded ({payment.receipt_number}).")
        return redirect('payment_list')

    return render(request, 'workshop/payments/list.html', {'payments': payments, 'orders': orders, 'methods': PaymentMethod.choices})

@login_required
def payment_receipt_print(request, receipt_number):
    payment = get_object_or_404(Payment.objects.select_related('order', 'customer', 'received_by'), receipt_number=receipt_number)
    return render(request, 'workshop/payments/receipt.html', {'payment': payment})


# --- DELIVERY WORKFLOW ---
@login_required
def delivery_record_view(request, job_id):
    job = get_object_or_404(Job.objects.select_related('order', 'order__customer'), job_id=job_id)

    if request.method == 'POST':
        receiver = request.POST.get('delivered_to_name', job.order.customer.name)
        notes = request.POST.get('notes', '')

        delivery = Delivery.objects.create(
            job=job,
            delivered_to_name=receiver,
            delivered_by=request.user,
            notes=notes
        )

        job.overall_status = JobOverallStatus.DELIVERED
        job.current_stage = StageCode.DELIVERED
        job.current_location = PhysicalLocation.CUSTOMER_HANDS
        job.save()

        # Check if all jobs in this order are delivered
        order = job.order
        if order.jobs.exclude(overall_status=JobOverallStatus.DELIVERED).count() == 0:
            order.status = OrderStatus.DELIVERED
            order.save()

        log_audit(request.user, "Recorded Delivery", delivery, f"Delivered to {receiver}", request)
        messages.success(request, f"Jewellery {job.job_id} successfully marked as Delivered.")
        return redirect('job_detail', job_id=job.job_id)

    return render(request, 'workshop/jobs/delivery_confirm.html', {'job': job})


# --- REPORTS & EXCEL EXPORTS ---
@login_required
def daily_report_view(request):
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()
    orders_today = Order.objects.filter(created_at__date=today)
    completed_today = Job.objects.filter(completion_date__date=today)
    gold_txns_today = GoldTransaction.objects.filter(created_at__date=today)
    payments_today = Payment.objects.filter(date=today)

    total_revenue_today = sum(p.amount for p in payments_today) or Decimal('0.00')

    context = {
        'report_date': today,
        'orders_today': orders_today,
        'completed_today': completed_today,
        'gold_txns_today': gold_txns_today,
        'payments_today': payments_today,
        'total_revenue_today': total_revenue_today,
    }
    return render(request, 'workshop/reports/daily.html', context)

@login_required
def export_jobs_excel_view(request):
    excel_buffer = export_jobs_to_excel()
    response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Jobs_Master_Export.xlsx"'
    return response

@login_required
def export_gold_excel_view(request):
    excel_buffer = export_gold_ledger_to_excel()
    response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Gold_Accountability_Ledger.xlsx"'
    return response


# --- BACKUP CENTER ---
@login_required
def backup_center_view(request):
    backups = BackupRecord.objects.all().order_by('-created_at')
    db_size = os.path.getsize(settings.DATABASES['default']['NAME']) if os.path.exists(settings.DATABASES['default']['NAME']) else 0

    if request.method == 'POST' and 'backup_now' in request.POST:
        record = perform_system_backup(notes=f"Manual backup initiated by {request.user.username}")
        log_audit(request.user, "Created System Backup", None, f"File: {record.backup_file}", request)
        messages.success(request, f"Backup created successfully: {record.backup_file} ({record.file_size_display})")
        return redirect('backup_center')

    return render(request, 'workshop/backup/center.html', {
        'backups': backups,
        'db_size_kb': round(db_size / 1024, 1),
        'last_backup': backups.first() if backups.exists() else None
    })


# --- AUDIT LOGS ---
@login_required
def audit_logs_view(request):
    logs = AuditLog.objects.all().select_related('user').order_by('-timestamp')[:100]
    return render(request, 'workshop/audit/logs.html', {'logs': logs})


# --- SETTINGS ---
@login_required
def settings_view(request):
    settings_obj = WorkshopSettings.objects.first()
    if not settings_obj:
        settings_obj = WorkshopSettings.objects.create()

    if request.method == 'POST':
        settings_obj.name = request.POST.get('name', settings_obj.name)
        settings_obj.tagline = request.POST.get('tagline', settings_obj.tagline)
        settings_obj.address = request.POST.get('address', settings_obj.address)
        settings_obj.phone = request.POST.get('phone', settings_obj.phone)
        settings_obj.email = request.POST.get('email', settings_obj.email)
        settings_obj.currency_symbol = request.POST.get('currency_symbol', settings_obj.currency_symbol)
        settings_obj.gst_number = request.POST.get('gst_number', settings_obj.gst_number)
        settings_obj.default_purity = request.POST.get('default_purity', settings_obj.default_purity)
        settings_obj.save()

        log_audit(request.user, "Updated Workshop Settings", None, "Settings updated", request)
        messages.success(request, "Workshop settings saved successfully.")
        return redirect('settings')

    return render(request, 'workshop/settings/settings.html', {'settings': settings_obj})


# --- API / QUICK SEARCH / AJAX ACTIONS ---
@login_required
def api_quick_search(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    results = []

    # 1. Jobs
    jobs = Job.objects.filter(
        is_deleted=False
    ).filter(
        Q(job_id__icontains=q) | Q(title__icontains=q)
    ).select_related('order__customer', 'current_worker')[:5]
    for j in jobs:
        results.append({
            'type': 'JOB',
            'title': f"{j.job_id} — {j.title}",
            'subtitle': f"Customer: {j.order.customer.name} | Stage: {j.get_current_stage_display()}",
            'meta': f"{j.gold_purity} | {j.expected_weight}g",
            'url': f"/jobs/{j.job_id}/"
        })

    # 2. Customers (Top Priority in search)
    custs = Customer.objects.filter(
        is_deleted=False
    ).filter(
        Q(name__icontains=q) | Q(mobile__icontains=q) | Q(customer_id__icontains=q)
    )[:5]
    for c in custs:
        results.append({
            'type': 'CUSTOMER',
            'title': f"{c.name} ({c.customer_id})",
            'subtitle': f"Phone: {c.mobile} | Active Orders: {c.active_orders}",
            'meta': f"Balance: ₹{c.outstanding_balance}",
            'url': f"/customers/{c.pk}/"
        })

    # 3. Orders
    orders = Order.objects.filter(
        is_deleted=False
    ).filter(
        Q(order_number__icontains=q)
    ).select_related('customer')[:4]
    for o in orders:
        results.append({
            'type': 'ORDER',
            'title': f"{o.order_number}",
            'subtitle': f"Client: {o.customer.name} | Status: {o.get_status_display()}",
            'meta': f"₹{o.total_estimated_amount}",
            'url': f"/orders/{o.pk}/"
        })

    return JsonResponse({'results': results})


@login_required
@require_POST
def api_stage_action(request, job_id):
    """
    Unified stage action handler for all job workflow transitions.
    Handles Karigar bench actions AND Atelier polisher/stone/complete workflow.
    Called via fetch() from the job detail page — always returns JSON.

    Actions:
      start_work        — Begin work on current stage
      pause_work        — Pause / waiting
      resume_work       — Resume after pause
      advance_stage     — Complete current stage and move to next
      give_polisher     — Hand piece to polisher
      receive_polisher  — Receive back from polisher
      give_stone        — Hand piece to stone fitter
      receive_stone     — Receive back from stone fitter
      complete_job      — Mark job Completed & Ready for Customer
    """
    import json
    try:
        body = json.loads(request.body)
        action = body.get('action')
    except Exception:
        action = request.POST.get('action')

    job = get_object_or_404(Job, job_id=job_id)
    history = job.stage_histories.filter(stage_name=job.current_stage).order_by('-assigned_at').first()
    now = timezone.now()

    # ── Karigar Bench Actions ──────────────────────────────────────────────────
    if action in ('start', 'start_work'):
        job.overall_status = JobOverallStatus.IN_PROGRESS
        job.start_date = job.start_date or now
        job.save()
        if history:
            history.status = StageStatus.IN_PROGRESS
            history.start_time = history.start_time or now
            history.save()
        log_audit(request.user, "Started Work", job, f"Stage: {job.current_stage}", request)
        return JsonResponse({'success': True, 'message': f"Work started on {job.job_id}."})

    elif action in ('pause', 'pause_work'):
        job.overall_status = JobOverallStatus.WAITING
        job.waiting_reason = "Karigar paused work"
        job.save()
        if history:
            history.status = StageStatus.PAUSED
            history.pause_time = now
            history.save()
        log_audit(request.user, "Paused Work", job, f"Stage: {job.current_stage}", request)
        return JsonResponse({'success': True, 'message': f"Work paused on {job.job_id}."})

    elif action in ('resume', 'resume_work'):
        job.overall_status = JobOverallStatus.IN_PROGRESS
        job.waiting_reason = ""
        job.save()
        if history:
            history.status = StageStatus.IN_PROGRESS
            history.resume_time = now
            history.save()
        log_audit(request.user, "Resumed Work", job, f"Stage: {job.current_stage}", request)
        return JsonResponse({'success': True, 'message': f"Work resumed on {job.job_id}."})

    elif action in ('complete', 'next_stage', 'advance_stage'):
        if history:
            history.status = StageStatus.COMPLETED
            history.completion_time = now
            history.calculate_actual_duration()
            history.save()

        stage_sequence = [
            StageCode.ORDER_RECEIVED, StageCode.GOLD_ISSUED, StageCode.MAKING,
            StageCode.STONE_SETTING, StageCode.POLISHING, StageCode.QUALITY_CHECK,
            StageCode.READY, StageCode.DELIVERED
        ]
        try:
            current_idx = stage_sequence.index(job.current_stage)
            next_stage = stage_sequence[current_idx + 1] if current_idx + 1 < len(stage_sequence) else StageCode.QUALITY_CHECK
        except ValueError:
            next_stage = StageCode.QUALITY_CHECK

        job.current_stage = next_stage
        if next_stage == StageCode.QUALITY_CHECK:
            job.overall_status = JobOverallStatus.QC_PENDING
            job.current_location = PhysicalLocation.QC_DESK
        elif next_stage == StageCode.READY:
            job.overall_status = JobOverallStatus.READY
            job.current_location = PhysicalLocation.READY_DISPLAY
        else:
            job.overall_status = JobOverallStatus.IN_PROGRESS
        job.save()

        JobStageHistory.objects.create(
            job=job,
            stage_name=next_stage,
            worker=None,
            assigned_by=request.user,
            status=StageStatus.PENDING
        )
        log_audit(request.user, "Moved Stage", job, f"Moved to {next_stage}", request)
        return JsonResponse({'success': True, 'message': f"Moved to {job.get_current_stage_display()}."})

    # ── Atelier Polisher / Stone / Completion Workflow ─────────────────────────
    elif action == 'give_polisher':
        job.atelier_stage = 'AT_POLISHER'
        job.polisher_given_date = now
        job.current_stage = StageCode.POLISHING
        job.overall_status = JobOverallStatus.IN_PROGRESS
        job.save()
        return JsonResponse({'success': True, 'message': f'Job {job.job_id} handed to Polish Worker.', 'stage': 'AT_POLISHER'})

    elif action == 'receive_polisher':
        job.atelier_stage = 'POLISH_DONE'
        job.polisher_received_date = now
        job.save()
        return JsonResponse({'success': True, 'message': f'Job {job.job_id} received from Polish Worker.', 'stage': 'POLISH_DONE'})

    elif action == 'give_stone':
        job.atelier_stage = 'AT_STONE'
        job.stone_given_date = now
        job.current_stage = StageCode.STONE_SETTING
        job.overall_status = JobOverallStatus.IN_PROGRESS
        job.save()
        return JsonResponse({'success': True, 'message': f'Job {job.job_id} handed to Stone Fitter.', 'stage': 'AT_STONE'})

    elif action == 'receive_stone':
        job.atelier_stage = 'STONE_DONE'
        job.stone_received_date = now
        job.save()
        return JsonResponse({'success': True, 'message': f'Job {job.job_id} received from Stone Fitter.', 'stage': 'STONE_DONE'})

    elif action == 'complete_job' or request.FILES.get('final_photo') or request.FILES.get('photo_file'):
        photo_file = request.FILES.get('final_photo') or request.FILES.get('photo_file')
        uploaded_photo = None
        if photo_file:
            try:
                user = request.user if request.user.is_authenticated else None
                category = request.POST.get('photo_category', PhotoCategory.FINAL_FRONT)
                uploaded_photo = JobPhoto.objects.create(
                    job=job,
                    category=category,
                    image=photo_file,
                    caption=request.POST.get('caption', 'Final Output Piece'),
                    uploaded_by=user,
                    worker=job.current_worker
                )
                qc = getattr(job, 'quality_check', None)
                if qc:
                    qc.final_photo_uploaded = True
                    qc.save()
                log_audit(user, "Uploaded Final Output Photo", job, f"File: {photo_file.name}", request)
            except Exception as e:
                print(f"Error saving final output photo: {e}")

        job.atelier_stage = 'COMPLETED'
        job.completion_date = job.completion_date or now
        job.overall_status = JobOverallStatus.READY
        job.save()

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.content_type == 'application/json'
        if not is_ajax:
            messages.success(request, f"Final output photograph recorded and job {job.job_id} marked Ready.")
            return redirect(request.META.get('HTTP_REFERER') or reverse('job_detail', args=[job.job_id]))

        return JsonResponse({
            'success': True,
            'message': f'Job {job.job_id} marked Completed & Final Output Photo recorded.',
            'stage': 'COMPLETED',
            'photo_url': (uploaded_photo.image.url if uploaded_photo and uploaded_photo.image else (job.final_photo or ''))
        })

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.content_type == 'application/json'
    if not is_ajax:
        messages.error(request, f"Unknown action: {action}")
        return redirect(request.META.get('HTTP_REFERER') or reverse('job_detail', args=[job.job_id]))

    return JsonResponse({'success': False, 'error': f'Unknown action: {action}'}, status=400)


# --- SOFT DELETE & RECYCLE BIN MANAGEMENT ---
@login_required
@require_POST
def item_soft_delete(request, item_type, pk):
    """Soft delete: moves item to the Recycle Bin instead of permanent deletion"""
    now = timezone.now()
    item_title = ""
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'

    if item_type == 'customer':
        item = get_object_or_404(Customer, pk=pk)
        item.is_deleted = True
        item.deleted_at = now
        item.save()
        item_title = f"Customer '{item.name}'"
        log_audit(request.user, "Moved to Recycle Bin", item, f"Soft-deleted {item.name}", request)
        next_url = request.POST.get('next') or '/customers/'

    elif item_type == 'order':
        item = get_object_or_404(Order, pk=pk)
        item.is_deleted = True
        item.deleted_at = now
        item.save()
        # Also soft delete child jobs
        item.jobs.update(is_deleted=True, deleted_at=now)
        item_title = f"Order '{item.order_number}'"
        log_audit(request.user, "Moved to Recycle Bin", item, f"Soft-deleted {item.order_number}", request)
        next_url = request.POST.get('next') or '/orders/'

    elif item_type == 'job':
        item = get_object_or_404(Job, pk=pk)
        item.is_deleted = True
        item.deleted_at = now
        item.save()
        item_title = f"Job '{item.job_id} ({item.title})'"
        log_audit(request.user, "Moved to Recycle Bin", item, f"Soft-deleted {item.job_id}", request)
        next_url = request.POST.get('next') or '/jobs/'

    messages.success(request, f"{item_title} moved to Recycle Bin. You can restore it anytime or delete it permanently.")
    return redirect(next_url)


@login_required
def recycle_bin_view(request):
    """Displays all soft-deleted Customers, Orders, and Jobs with options to Restore or Delete Permanently"""
    deleted_customers = Customer.objects.filter(is_deleted=True).order_by('-deleted_at')
    deleted_orders = Order.objects.filter(is_deleted=True).select_related('customer').order_by('-deleted_at')
    deleted_jobs = Job.objects.filter(is_deleted=True).select_related('order', 'order__customer').order_by('-deleted_at')

    total_count = deleted_customers.count() + deleted_orders.count() + deleted_jobs.count()

    context = {
        'deleted_customers': deleted_customers,
        'deleted_orders': deleted_orders,
        'deleted_jobs': deleted_jobs,
        'total_count': total_count,
    }
    return render(request, 'workshop/recycle_bin.html', context)


@login_required
@require_POST
def recycle_bin_restore(request, item_type, pk):
    """Restores item from Recycle Bin back to active status"""
    item_title = ""
    if item_type == 'customer':
        item = get_object_or_404(Customer, pk=pk)
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        item_title = f"Customer '{item.name}'"
        log_audit(request.user, "Restored from Recycle Bin", item, f"Restored {item.name}", request)

    elif item_type == 'order':
        item = get_object_or_404(Order, pk=pk)
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        item.jobs.update(is_deleted=False, deleted_at=None)
        item_title = f"Order '{item.order_number}'"
        log_audit(request.user, "Restored from Recycle Bin", item, f"Restored {item.order_number}", request)

    elif item_type == 'job':
        item = get_object_or_404(Job, pk=pk)
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        item_title = f"Job '{item.job_id}'"
        log_audit(request.user, "Restored from Recycle Bin", item, f"Restored {item.job_id}", request)

    messages.success(request, f"{item_title} successfully restored to active records.")
    return redirect('recycle_bin')


@login_required
@require_POST
def recycle_bin_delete_permanent(request, item_type, pk):
    """Permanently deletes item from the database"""
    item_title = ""
    if item_type == 'customer':
        item = get_object_or_404(Customer, pk=pk)
        item_title = f"Customer '{item.name}'"
        log_audit(request.user, "Permanently Deleted", None, f"Deleted Customer {item.name} ({item.customer_id})", request)
        item.delete()

    elif item_type == 'order':
        item = get_object_or_404(Order, pk=pk)
        item_title = f"Order '{item.order_number}'"
        log_audit(request.user, "Permanently Deleted", None, f"Deleted Order {item.order_number}", request)
        item.delete()

    elif item_type == 'job':
        item = get_object_or_404(Job, pk=pk)
        item_title = f"Job '{item.job_id}'"
        log_audit(request.user, "Permanently Deleted", None, f"Deleted Job {item.job_id}", request)
        item.delete()

    messages.success(request, f"{item_title} was permanently removed.")
    return redirect('recycle_bin')


@login_required
@require_POST
def recycle_bin_empty(request):
    """Empty entire Recycle Bin in one click"""
    c_count = Customer.objects.filter(is_deleted=True).count()
    o_count = Order.objects.filter(is_deleted=True).count()
    j_count = Job.objects.filter(is_deleted=True).count()

    Customer.objects.filter(is_deleted=True).delete()
    Order.objects.filter(is_deleted=True).delete()
    Job.objects.filter(is_deleted=True).delete()

    log_audit(request.user, "Emptied Recycle Bin", None, f"Permanently deleted {c_count} customers, {o_count} orders, {j_count} jobs", request)
    messages.success(request, f"Recycle Bin completely emptied ({c_count + o_count + j_count} items purged).")
    return redirect('recycle_bin')


# --- ITEM-SPECIFIC DIGITAL DOSSIER (ACCESSIBLE VIA QR CODE) ---
def job_dossier_view(request, job_id):
    """Public / Atelier Item Dossier Card opened by scanning the Item's QR code.
       Contains: Item present details, Customer name & phone, given date, return date,
       weight, finishing status, finishing photograph, and verification status."""
    job = get_object_or_404(
        Job.objects.select_related('order', 'order__customer', 'current_worker'),
        job_id=job_id
    )
    customer = job.order.customer if job.order else None
    ref_photo = job.reference_photo
    final_photo = job.final_photo
    photos = job.photos.all().order_by('-created_at')

    # Refresh legacy text/relative QR codes so every camera opens this live dossier.
    _refresh_job_qr(job, request)

    context = {
        'job': job,
        'customer': customer,
        'ref_photo': ref_photo,
        'final_photo': final_photo,
        'photos': photos,
    }
    return render(request, 'workshop/jobs/dossier.html', context)


# --- LIVE BULLION RATES API & LIVE BENCHMARKS ---
def api_live_rates(request):
    """Returns accurate live Gold and Silver rates with priority for Chennai & Bangalore"""
    rates = get_or_seed_rates()
    today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()
    data = {
        'date': today.strftime('%d %B %Y'),
        'timestamp': timezone.now().strftime('%H:%M:%S'),
        'chennai': {
            'gold_24k': float(rates['CHENNAI'].gold_24k_per_gram),
            'gold_22k': float(rates['CHENNAI'].gold_22k_per_gram),
            'gold_18k': float(rates['CHENNAI'].gold_18k_per_gram),
            'silver_per_gram': float(rates['CHENNAI'].silver_per_gram),
            'silver_per_kg': float(rates['CHENNAI'].silver_per_kg),
            'source': rates['CHENNAI'].source,
        },
        'bangalore': {
            'gold_24k': float(rates['BANGALORE'].gold_24k_per_gram),
            'gold_22k': float(rates['BANGALORE'].gold_22k_per_gram),
            'gold_18k': float(rates['BANGALORE'].gold_18k_per_gram),
            'silver_per_gram': float(rates['BANGALORE'].silver_per_gram),
            'silver_per_kg': float(rates['BANGALORE'].silver_per_kg),
            'source': rates['BANGALORE'].source,
        }
    }
    return JsonResponse(data)


@login_required
@require_POST
def api_update_rates(request):
    """Allows user to refresh or manually update benchmark rates"""
    city = request.POST.get('city', 'CHENNAI').upper()
    gold_24k = request.POST.get('gold_24k')
    gold_22k = request.POST.get('gold_22k')
    silver_g = request.POST.get('silver_per_gram')

    today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()
    rate_obj = DailyMarketRate.objects.filter(city=city, rate_date=today).first()
    if not rate_obj:
        rate_obj = DailyMarketRate(city=city, rate_date=today)

    if gold_24k:
        rate_obj.gold_24k_per_gram = Decimal(gold_24k)
    if gold_22k:
        rate_obj.gold_22k_per_gram = Decimal(gold_22k)
    if silver_g:
        rate_obj.silver_per_gram = Decimal(silver_g)
        rate_obj.silver_per_kg = Decimal(silver_g) * 1000

    rate_obj.source = "Workshop Manual Override"
    rate_obj.save()

    messages.success(request, f"Updated {city} market rates: 22K ₹{rate_obj.gold_22k_per_gram}/g, Silver ₹{rate_obj.silver_per_gram}/g.")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# --- ADD ITEM TO EXISTING CUSTOMER ---
@login_required
@require_POST
def customer_add_item(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    j_type = request.POST.get('jewellery_type', JewelleryType.RING)
    custom_name = request.POST.get('custom_type_name', '').strip()
    purity = request.POST.get('gold_purity', GoldPurity.P_22K)
    weight_str = request.POST.get('expected_weight', '0').strip()
    weight = Decimal(weight_str) if weight_str else Decimal('0.000')
    requirements = request.POST.get('requirements', '').strip()

    title = custom_name if (j_type == JewelleryType.OTHER and custom_name) else f"{purity} {dict(JewelleryType.choices).get(j_type, j_type.title())}"

    order = Order.objects.create(
        customer=customer,
        order_type=OrderType.NEW_JEWELLERY,
        priority=PriorityLevel.NORMAL,
        customer_instructions=requirements,
        status=OrderStatus.IN_PROGRESS
    )

    job = Job.objects.create(
        order=order,
        jewellery_type=j_type,
        custom_type_name=custom_name,
        title=title,
        gold_purity=purity,
        expected_weight=weight,
        special_instructions=requirements,
        atelier_stage='RECEIVED',
        current_stage=StageCode.ORDER_RECEIVED,
        overall_status=JobOverallStatus.IN_PROGRESS
    )

    if 'reference_photo' in request.FILES:
        JobPhoto.objects.create(
            job=job,
            image=request.FILES['reference_photo'],
            category=PhotoCategory.CUSTOMER_REF,
            caption=f"Reference picture for {title}",
            uploaded_by=request.user if request.user.is_authenticated else None
        )

    messages.success(request, f"Added item {title} ({job.job_id}) to {customer.name}.")
    return redirect('customer_detail', pk=customer.pk)


# --- CUSTOMER QR BILL / VERIFICATION PRINT ---
def customer_qr_bill(request, pk):
    """Clean printable Customer QR Bill containing customer info, item details,
       reference picture, final finished picture, weights, purity, and scannable QR verification."""
    customer = get_object_or_404(Customer, pk=pk)
    orders = customer.orders.filter(is_deleted=False).prefetch_related('jobs', 'jobs__photos')
    all_jobs = []
    for o in orders:
        for j in o.jobs.filter(is_deleted=False):
            all_jobs.append(j)

    context = {
        'customer': customer,
        'orders': orders,
        'jobs': all_jobs,
        'today': timezone.localdate() if timezone.is_aware(timezone.now()) else date.today(),
        'settings': WorkshopSettings.objects.first()
    }
    # This is a separate customer-level QR: it opens the complete printable bill,
    # even when the customer has no jobs or the legacy job QR is missing.
    bill_url = request.build_absolute_uri(reverse('customer_qr_bill_pdf', kwargs={'pk': customer.pk}))
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=8, border=4)
    qr.add_data(bill_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color='#000000', back_color='#ffffff')
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format='PNG')
    context['customer_bill_qr'] = 'data:image/png;base64,' + base64.b64encode(qr_buffer.getvalue()).decode('ascii')
    return render(request, 'workshop/customers/qr_bill.html', context)


def customer_qr_bill_pdf(request, pk):
    """Serve the bill as an inline PDF so phone cameras open a usable document."""
    customer = get_object_or_404(Customer, pk=pk)
    jobs = list(Job.objects.filter(order__customer=customer, is_deleted=False, order__is_deleted=False)
                .select_related('order').order_by('order__created_at', 'created_at'))
    workshop_settings = WorkshopSettings.objects.first()
    bill_url = request.build_absolute_uri(reverse('customer_qr_bill_pdf', kwargs={'pk': customer.pk}))
    stream = io.BytesIO()
    gold = colors.HexColor('#b8892a')
    muted = colors.HexColor('#626262')
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm,
                            topMargin=16*mm, bottomMargin=18*mm,
                            title=f'Customer Bill - {customer.name}',
                            author=workshop_settings.name if workshop_settings else 'GSCMS')
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name='BillBrand', parent=base['Title'], fontName='Helvetica-Bold',
                            fontSize=19, leading=23, alignment=0, textColor=colors.HexColor('#171717'),
                            spaceAfter=4))
    base.add(ParagraphStyle(name='BillSmall', parent=base['BodyText'], fontSize=8.5, leading=12,
                            textColor=muted))
    base.add(ParagraphStyle(name='BillCell', parent=base['BodyText'], fontSize=8.5, leading=11,
                            textColor=colors.HexColor('#202020')))
    base.add(ParagraphStyle(name='BillCellSmall', parent=base['BodyText'], fontSize=7.5, leading=10,
                            textColor=muted))
    esc = lambda value: (str(value or '-').replace('&', '&amp;').replace('<', '&lt;')
                         .replace('>', '&gt;').replace('\n', '<br/>'))
    story = [Paragraph('FINE JEWELLERY WORKSHOP', base['BillSmall']),
             Paragraph(esc(workshop_settings.name if workshop_settings else 'GSCMS Fine Jewellery Workshop'), base['BillBrand'])]
    details = []
    if workshop_settings:
        details.extend([esc(workshop_settings.address), f'Phone: {esc(workshop_settings.phone)}'])
        if workshop_settings.gst_number:
            details.append(f'GSTIN: {esc(workshop_settings.gst_number)}')
    if details:
        story.append(Paragraph('<br/>'.join(details), base['BillSmall']))
    story.extend([Spacer(1, 7*mm), Paragraph('CUSTOMER BILL &amp; ITEM CERTIFICATE', base['Heading2']),
                  Paragraph(f"Bill reference: {esc(customer.customer_id)} &nbsp; | &nbsp; Date: {(timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()):%d %b %Y}", base['BillSmall']),
                  Spacer(1, 3*mm)])

    customer_rows = [
        [Paragraph('<b>Customer</b>', base['BillCellSmall']), Paragraph(esc(customer.name), base['BillCell'])],
        [Paragraph('<b>Mobile</b>', base['BillCellSmall']), Paragraph(esc(customer.mobile), base['BillCell'])],
        [Paragraph('<b>Address</b>', base['BillCellSmall']), Paragraph(esc(customer.address), base['BillCell'])],
    ]
    if customer.alternate_mobile:
        customer_rows.append([Paragraph('<b>Alternate mobile</b>', base['BillCellSmall']), Paragraph(esc(customer.alternate_mobile), base['BillCell'])])
    contact = Table(customer_rows, colWidths=[34*mm, 142*mm])
    contact.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f7f5f0')),
                                 ('BOX',(0,0),(-1,-1),.5,colors.HexColor('#dedbd4')),
                                 ('INNERGRID',(0,0),(-1,-1),.3,colors.HexColor('#dedbd4')),
                                 ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
                                 ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),
                                 ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.extend([contact, Spacer(1, 6*mm), Paragraph('Jewellery items and specifications', base['Heading2']), Spacer(1, 2*mm)])

    rows = [[Paragraph(f'<b>{label}</b>', base['BillCell']) for label in
             ('Item / Job ID', 'Purity', 'Expected wt.', 'Final wt.', 'Stage')]]
    for job in jobs:
        rows.append([
            Paragraph(f"<b>{esc(job.title)}</b><br/><font size='7'>{esc(job.job_id)} | {esc(job.get_jewellery_type_display())}</font>", base['BillCell']),
            Paragraph(esc(job.gold_purity), base['BillCell']),
            Paragraph(f'{job.expected_weight} g', base['BillCell']),
            Paragraph(f'{job.final_gross_weight} g' if job.final_gross_weight is not None else 'Pending', base['BillCell']),
            Paragraph(esc(job.get_current_stage_display()), base['BillCell']),
        ])
    if not jobs:
        rows.append([Paragraph('No jewellery items are recorded for this customer.', base['BillCellSmall']), '', '', '', ''])
    items = Table(rows, colWidths=[68*mm, 22*mm, 28*mm, 26*mm, 32*mm], repeatRows=1)
    items.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f0e7d2')),
                               ('LINEBELOW',(0,0),(-1,0),1,gold),
                               ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#faf9f6')]),
                               ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#dedbd4')),
                               ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),
                               ('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),7),
                               ('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(items)
    for job in jobs:
        if job.special_instructions:
            story.extend([Spacer(1, 2*mm), Paragraph(f'<b>{esc(job.job_id)} - Instructions:</b> {esc(job.special_instructions)}', base['BillCellSmall'])])
        photo_categories = {
            'Reference photo': ['REFERENCE', 'REFERENCE_FRONT', 'REFERENCE_SIDE', 'REFERENCE_BACK', 'REFERENCE_SKETCH', 'CUSTOMER_REF'],
            'Finished photo': ['FINAL_PIECE', 'FINAL_FRONT', 'FINAL_SIDE', 'FINAL_BACK', 'FINAL_CLOSEUP', 'STONE_DETAIL', 'PACKAGING'],
        }
        photo_cells = []
        for label, categories in photo_categories.items():
            photo = job.photos.filter(category__in=categories).exclude(image='').first()
            if not photo:
                continue
            try:
                photo.image.open('rb')
                photo_stream = io.BytesIO(photo.image.read())
                photo.image.close()
                photo_stream.seek(0)
                photo_cells.append([Paragraph(f'<b>{esc(job.job_id)} {label}</b>', base['BillCellSmall']),
                                    PDFImage(photo_stream, width=32*mm, height=25*mm, kind='proportional')])
            except Exception:
                continue
        if photo_cells:
            story.extend([Spacer(1, 3*mm), Paragraph('Item photos', base['BillCellSmall'])])
            photo_table = Table(photo_cells, colWidths=[54*mm, 38*mm], hAlign='LEFT')
            photo_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                             ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#faf9f6')),
                                             ('BOX',(0,0),(-1,-1),.35,colors.HexColor('#dedbd4')),
                                             ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
                                             ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
            story.append(photo_table)
    if jobs:
        expected = sum((job.expected_weight for job in jobs), Decimal('0.000'))
        finals = [job.final_gross_weight for job in jobs if job.final_gross_weight is not None]
        totals = f'<b>Items:</b> {len(jobs)} &nbsp; | &nbsp; <b>Total expected:</b> {expected:.3f} g'
        if finals:
            totals += f' &nbsp; | &nbsp; <b>Recorded final:</b> {sum(finals, Decimal("0.000")):.3f} g'
        story.extend([Spacer(1, 3*mm), Paragraph(totals, base['BillSmall'])])

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=4)
    qr.add_data(bill_url)
    qr.make(fit=True)
    qr_data = io.BytesIO()
    qr.make_image(fill_color='#000000', back_color='#ffffff').save(qr_data, format='PNG')
    qr_data.seek(0)
    story.extend([Spacer(1, 9*mm), Paragraph('Verified digital copy', base['Heading3']),
                  PDFImage(qr_data, width=28*mm, height=28*mm),
                  Paragraph('Scan to reopen this complete customer bill PDF.', base['BillSmall']),
                  Spacer(1, 3*mm), Paragraph('Thank you for choosing our workshop.', base['BillCell'])])

    def draw_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(gold)
        canvas.line(16*mm, 13*mm, A4[0]-16*mm, 13*mm)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(muted)
        canvas.drawString(16*mm, 8*mm, f'{customer.customer_id} - {customer.name[:45]}')
        canvas.drawRightString(A4[0]-16*mm, 8*mm, f'Page {document.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    response = HttpResponse(stream.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Customer_Bill_{customer.customer_id}.pdf"'
    response['Cache-Control'] = 'no-store'
    return response


# --- CLIENT DOCS GALLERY (3D INTERACTIVE CLIENT FOLDERS) ---
@login_required
def client_docs_view(request):
    """
    Dedicated Client Docs view rendering 3D interactive folders for each client.
    Each folder contains their documents (Order history, Job QR Dossiers, Reference & Final Photos, QR Bill)
    with Black, White, and Blue luxury atelier themes.
    """
    query = request.GET.get('q', '').strip()
    customers = Customer.objects.filter(is_deleted=False).prefetch_related('orders', 'orders__jobs', 'orders__jobs__photos').order_by('-created_at')
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(mobile__icontains=query) | Q(customer_id__icontains=query))

    client_folders = []
    for cust in customers:
        theme = 'black'
        jobs = []
        for o in cust.orders.filter(is_deleted=False):
            jobs.extend(list(o.jobs.filter(is_deleted=False)))

        client_folders.append({
            'customer': cust,
            'theme': theme,
            'jobs': jobs,
            'jobs_count': len(jobs),
            'latest_job': jobs[0] if jobs else None,
            'ref_photos_count': sum(1 for j in jobs if j.reference_photo),
            'final_photos_count': sum(1 for j in jobs if j.final_photo),
        })

    context = {
        'client_folders': client_folders,
        'query': query,
        'total_clients': len(client_folders)
    }
    return render(request, 'workshop/customers/docs.html', context)
