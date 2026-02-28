from django.contrib import admin
from .models import Vehicle, GarageInvoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ['item_name', 'quantity', 'unit_price', 'total_price', 'from_sale_receipt']
    readonly_fields = ['total_price']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'vehicle_model', 'owner_name', 'owner_phone', 'created_at']
    search_fields = ['plate_number', 'vehicle_model', 'owner_name', 'owner_phone']
    list_filter = ['created_at']
    ordering = ['-created_at']


@admin.register(GarageInvoice)
class GarageInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'vehicle', 'status', 'labor_charge', 'parts_total', 'total_amount', 'created_at']
    search_fields = ['invoice_number', 'vehicle__plate_number', 'sale_receipt_number']
    list_filter = ['status', 'created_at']
    readonly_fields = ['parts_total', 'total_amount', 'created_at', 'updated_at']
    inlines = [InvoiceItemInline]
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'vehicle', 'status')
        }),
        ('Repair Details', {
            'fields': ('repair_description', 'labor_charge')
        }),
        ('Parts Reference', {
            'fields': ('sale_receipt_number',)
        }),
        ('Totals', {
            'fields': ('parts_total', 'total_amount')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'completed_at')
        }),
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'item_name', 'quantity', 'unit_price', 'total_price', 'from_sale_receipt']
    search_fields = ['item_name', 'invoice__invoice_number', 'from_sale_receipt']
    list_filter = ['invoice__created_at']
    readonly_fields = ['total_price']
