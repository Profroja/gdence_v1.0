from django.contrib import admin
from .models import Customer, Sale, SaleItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'mobile_number', 'total_debt', 'total_purchases', 'is_active', 'created_at']
    search_fields = ['name', 'mobile_number']
    list_filter = ['is_active', 'created_at']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Customer Information', {
            'fields': ('name', 'mobile_number')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['total_price', 'created_at']
    fields = ['item_type', 'item_name', 'quantity', 'unit_price', 'total_price']
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'customer', 'sale_type', 'payment_type', 'total_amount', 'is_paid', 'remaining_debt', 'created_at']
    list_filter = ['sale_type', 'payment_type', 'is_paid', 'created_at']
    search_fields = ['receipt_number', 'customer__name', 'customer__mobile_number']
    readonly_fields = ['receipt_number', 'total_amount', 'remaining_debt', 'items_count', 'created_at', 'updated_at']
    inlines = [SaleItemInline]
    fieldsets = (
        ('Sale Information', {
            'fields': ('receipt_number', 'customer', 'sale_type', 'payment_type')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'discount', 'total_amount', 'items_count')
        }),
        ('Payment Tracking', {
            'fields': ('is_paid', 'paid_amount', 'remaining_debt')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new sale
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'item_type', 'item_name', 'quantity', 'unit_price', 'total_price', 'created_at']
    list_filter = ['item_type', 'created_at']
    search_fields = ['item_name', 'sale__receipt_number']
    readonly_fields = ['total_price', 'created_at']
    fieldsets = (
        ('Sale Information', {
            'fields': ('sale', 'item_type')
        }),
        ('Product Reference', {
            'fields': ('new_spare_part', 'used_spare_part', 'component')
        }),
        ('Sale Details', {
            'fields': ('item_name', 'quantity', 'unit_price', 'total_price')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
