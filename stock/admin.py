from django.contrib import admin
from .models import Category, NewSparePart, UsedSparePart, Component, Customer, Sale, SaleItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']


class ComponentInline(admin.TabularInline):
    model = Component
    extra = 1
    fields = ['name', 'description', 'unit_price', 'initial_quantity', 'current_quantity', 'sold_quantity', 'is_active']


@admin.register(NewSparePart)
class NewSparePartAdmin(admin.ModelAdmin):
    list_display = ['name', 'part_number', 'category', 'unit_price', 'current_quantity', 'sold_quantity', 'stock_status', 'is_active']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'part_number', 'description']
    list_editable = ['is_active']
    readonly_fields = ['sold_quantity', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('part_number', 'name', 'category', 'description')
        }),
        ('Pricing', {
            'fields': ('unit_price',)
        }),
        ('Inventory', {
            'fields': ('initial_quantity', 'current_quantity', 'sold_quantity', 'minimum_stock_level')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return "❌ Out of Stock"
        elif obj.is_low_stock:
            return "⚠️ Low Stock"
        return "✅ In Stock"
    stock_status.short_description = "Status"


@admin.register(UsedSparePart)
class UsedSparePartAdmin(admin.ModelAdmin):
    list_display = ['name', 'part_number', 'category', 'condition', 'whole_price', 'current_quantity', 'is_broken_down', 'stock_status', 'is_active']
    list_filter = ['category', 'condition', 'is_broken_down', 'can_be_broken_down', 'is_active', 'created_at']
    search_fields = ['name', 'part_number', 'description']
    list_editable = ['is_active']
    readonly_fields = ['sold_quantity', 'created_at', 'updated_at']
    inlines = [ComponentInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('part_number', 'name', 'category', 'description', 'condition')
        }),
        ('Pricing', {
            'fields': ('whole_price',)
        }),
        ('Inventory', {
            'fields': ('initial_quantity', 'current_quantity', 'sold_quantity')
        }),
        ('Component Options', {
            'fields': ('can_be_broken_down', 'is_broken_down')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return "❌ Out of Stock"
        return "✅ In Stock"
    stock_status.short_description = "Status"


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ['name', 'used_spare_part', 'unit_price', 'current_quantity', 'sold_quantity', 'stock_status', 'is_active']
    list_filter = ['used_spare_part', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'used_spare_part__name']
    list_editable = ['is_active']
    readonly_fields = ['sold_quantity', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('used_spare_part', 'name', 'description')
        }),
        ('Pricing', {
            'fields': ('unit_price',)
        }),
        ('Inventory', {
            'fields': ('initial_quantity', 'current_quantity', 'sold_quantity')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )
    
    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return "❌ Out of Stock"
        return "✅ In Stock"
    stock_status.short_description = "Status"
