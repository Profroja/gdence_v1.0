from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/edit/<int:user_id>/', views.staff_edit, name='staff_edit'),
    path('staff/toggle/<int:user_id>/', views.staff_toggle_active, name='staff_toggle_active'),
    
    # Read-only views
    path('products/', views.products, name='products'),
    path('all-sales/', views.all_sales, name='all_sales'),
    path('sale-details/<int:sale_id>/', views.sale_details, name='sale_details'),
    path('car-diagnosing/', views.car_diagnosing, name='car_diagnosing'),
    path('customer-debts/', views.customer_debts, name='customer_debts'),
    path('debt-details/<int:sale_id>/', views.debt_details, name='debt_details'),
    path('expenditure/', views.expenditure, name='expenditure'),
    path('opening-balance/', views.opening_balance, name='opening_balance'),
    path('funga-hesabu/', views.funga_hesabu, name='funga_hesabu'),
]
