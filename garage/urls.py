from django.urls import path
from . import views

app_name = 'garage'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('invoices/', views.invoices, name='invoices'),
    path('get-receipt/<str:receipt_number>/', views.get_receipt, name='get_receipt'),
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoice-details/<int:invoice_id>/', views.invoice_details, name='invoice_details'),
    path('download-invoice/<int:invoice_id>/', views.download_invoice, name='download_invoice'),
    path('mark-completed/<int:invoice_id>/', views.mark_completed, name='mark_completed'),
]
