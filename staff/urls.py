from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('new-sale/', views.new_sale, name='new_sale'),
    path('create-sale/', views.create_sale, name='create_sale'),
    path('all-sales/', views.all_sales, name='all_sales'),
    path('sale-details/<int:sale_id>/', views.sale_details, name='sale_details'),
    path('get-sale/<int:sale_id>/', views.sale_details, name='get_sale'),
    path('products/', views.products_view, name='products'),
    path('customer-debts/', views.customer_debts, name='customer_debts'),
    path('record-payment/<int:sale_id>/', views.record_payment, name='record_payment'),
    path('debt-details/<int:sale_id>/', views.debt_details, name='debt_details'),
    path('expenditure/', views.expenditure, name='expenditure'),
    path('add-expenditure/', views.add_expenditure, name='add_expenditure'),
    path('api/stock-status/', views.stock_status_api, name='stock_status_api'),
    path('car-diagnosing/', views.car_diagnosing, name='car_diagnosing'),
    path('add-car-diagnosis/', views.add_car_diagnosis, name='add_car_diagnosis'),
    path('garage-invoices/', views.garage_invoices, name='garage_invoices'),
    path('opening-balance/', views.opening_balance, name='opening_balance'),
    path('add-opening-balance/', views.add_opening_balance, name='add_opening_balance'),
    path('funga-hesabu/', views.funga_hesabu, name='funga_hesabu'),
    path('thermal-receipt/<int:sale_id>/', views.thermal_receipt, name='thermal_receipt'),
    path('authorize-stock/<int:sale_id>/', views.authorize_stock_release, name='authorize_stock'),
    path('stock-authorization-receipt/<int:sale_id>/', views.stock_authorization_receipt, name='stock_authorization_receipt'),
    path('debt-bill-receipt/<int:sale_id>/', views.debt_bill_receipt, name='debt_bill_receipt'),
]
