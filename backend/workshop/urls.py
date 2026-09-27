from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('api/index.py', views.dashboard_view),

    # Customers & Client Documents
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/new/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/add-item/', views.customer_add_item, name='customer_add_item'),
    path('customers/<int:pk>/qr-bill/', views.customer_qr_bill, name='customer_qr_bill'),
    path('customers/<int:pk>/qr-bill.pdf', views.customer_qr_bill_pdf, name='customer_qr_bill_pdf'),
    path('client-docs/', views.client_docs_view, name='client_docs'),

    # Orders
    path('orders/', views.order_list, name='order_list'),
    path('orders/new/', views.order_create, name='order_create'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),

    # Jobs & Production
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<str:job_id>/', views.job_detail, name='job_detail'),
    path('jobs/<str:job_id>/dossier/', views.job_dossier_view, name='job_dossier'),
    path('jobs/<str:job_id>/card/', views.job_card_print, name='job_card_print'),
    path('jobs/<str:job_id>/comparison/', views.job_comparison_view, name='job_comparison'),
    path('jobs/<str:job_id>/export-zip/', views.job_export_zip, name='job_export_zip'),
    path('jobs/<str:job_id>/delivery/', views.delivery_record_view, name='delivery_record'),

    # Soft Delete & Recycle Bin
    path('delete/<str:item_type>/<int:pk>/', views.item_soft_delete, name='item_soft_delete'),
    path('recycle-bin/', views.recycle_bin_view, name='recycle_bin'),
    path('recycle-bin/restore/<str:item_type>/<int:pk>/', views.recycle_bin_restore, name='recycle_bin_restore'),
    path('recycle-bin/delete/<str:item_type>/<int:pk>/', views.recycle_bin_delete_permanent, name='recycle_bin_delete_permanent'),
    path('recycle-bin/empty/', views.recycle_bin_empty, name='recycle_bin_empty'),

    # Workers & Touch Station
    path('workers/', views.worker_list, name='worker_list'),
    path('station/', views.worker_station, name='worker_station'),
    path('station/<str:worker_id>/', views.worker_station, name='worker_station_worker'),

    # Gold Accountability Ledger
    path('gold/', views.gold_ledger_view, name='gold_ledger'),
    path('gold/export/', views.export_gold_excel_view, name='export_gold_excel'),

    # Stone Inventory
    path('stones/', views.stone_inventory_view, name='stone_inventory'),

    # Quality Control
    path('qc/', views.qc_desk_view, name='qc_desk'),
    path('qc/<str:job_id>/', views.qc_inspect_job, name='qc_inspect'),

    # Payments & Invoices
    path('payments/', views.payment_list_view, name='payment_list'),
    path('payments/receipt/<str:receipt_number>/', views.payment_receipt_print, name='payment_receipt_print'),

    # Reports & Exports
    path('reports/daily/', views.daily_report_view, name='daily_report'),
    path('reports/jobs-export/', views.export_jobs_excel_view, name='export_jobs_excel'),

    # Backup Center
    path('backup/', views.backup_center_view, name='backup_center'),

    # Audit Trail
    path('audit/', views.audit_logs_view, name='audit_logs'),

    # Settings
    path('settings/', views.settings_view, name='settings'),

    # APIs & AJAX
    path('api/quick-search/', views.api_quick_search, name='api_quick_search'),
    path('api/live-rates/', views.api_live_rates, name='api_live_rates'),
    path('api/live-rates/update/', views.api_update_rates, name='api_update_rates'),
    path('api/jobs/<str:job_id>/stage-action/', views.api_stage_action, name='api_stage_action'),
]
