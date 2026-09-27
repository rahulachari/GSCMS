from datetime import date
from django.utils import timezone
from .models import WorkshopSettings, Job, Notification, Customer, Order

def workshop_globals(request):
    try:
        settings = WorkshopSettings.objects.first()
        if not settings:
            settings = WorkshopSettings(name="GSCMS", currency_symbol="₹")
    except Exception:
        settings = None

    unread_notifications = 0
    delayed_count = 0
    recycle_bin_count = 0
    
    try:
        recycle_bin_count = (
            Customer.objects.filter(is_deleted=True).count() +
            Order.objects.filter(is_deleted=True).count() +
            Job.objects.filter(is_deleted=True).count()
        )
    except Exception:
        recycle_bin_count = 0

    if request.user.is_authenticated:
        try:
            unread_notifications = Notification.objects.filter(is_read=False).count()
            delayed_count = Job.objects.filter(
                is_deleted=False,
                overall_status__in=['IN_PROGRESS', 'ASSIGNED', 'QC_PENDING']
            ).filter(is_delayed=True).count()
        except Exception:
            pass

    today = timezone.localdate() if timezone.is_aware(timezone.now()) else date.today()

    return {
        'workshop_settings': settings,
        'unread_notifications_count': unread_notifications,
        'delayed_jobs_count': delayed_count,
        'recycle_bin_count': recycle_bin_count,
        'current_market_date': today,
    }

