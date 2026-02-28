from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # All Spare Parts (Combined)
    path('all-spareparts/', views.all_spareparts, name='all_spareparts'),
    
    # New Spare Parts Management
    path('new-parts/', views.new_parts_list, name='new_parts_list'),
    path('new-parts/create/', views.new_part_create, name='new_part_create'),
    path('new-parts/edit/<int:pk>/', views.new_part_edit, name='new_part_edit'),
    path('new-parts/delete/<int:pk>/', views.new_part_delete, name='new_part_delete'),
    
    # Used Spare Parts Management
    path('used-parts/', views.used_parts_list, name='used_parts_list'),
    path('used-parts/create/', views.used_part_create, name='used_part_create'),
    path('used-parts/edit/<int:pk>/', views.used_part_edit, name='used_part_edit'),
    path('used-parts/delete/<int:pk>/', views.used_part_delete, name='used_part_delete'),
    
    # Components
    path('components/<int:used_part_id>/', views.components_list, name='components_list'),
    path('components/<int:used_part_id>/json/', views.components_json, name='components_json'),
    path('components/create/<int:used_part_id>/', views.component_create, name='component_create'),
    path('components/edit/<int:pk>/', views.component_edit, name='component_edit'),
    path('components/delete/<int:pk>/', views.component_delete, name='component_delete'),
    
    # Stock Management
    path('add-stock/<str:product_type>/<int:pk>/', views.add_stock, name='add_stock'),
    
    # Stock Releases
    path('stock-releases/', views.stock_releases, name='stock_releases'),
]
