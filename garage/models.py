from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


class Vehicle(models.Model):
    """Store vehicle information for garage services"""
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_model = models.CharField(max_length=100)  # e.g., "Toyota Corolla 2020"
    owner_name = models.CharField(max_length=100, blank=True, null=True)
    owner_phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['plate_number']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.plate_number} - {self.vehicle_model}"


class GarageInvoice(models.Model):
    """Garage service invoice with vehicle details and repair information"""
    invoice_number = models.CharField(max_length=50, unique=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='invoices')
    
    # Repair details
    repair_description = models.TextField(help_text="What was fixed on the vehicle")
    labor_charge = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))],
        default=0
    )
    
    # Sale reference for parts used
    sale_receipt_number = models.CharField(max_length=50, blank=True, null=True, help_text="Receipt number from sales")
    
    # Totals
    parts_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('paid', 'Paid'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps and user
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='garage_invoices')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Garage Invoice"
        verbose_name_plural = "Garage Invoices"
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]
    
    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.parts_total + self.labor_charge
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.invoice_number} - {self.vehicle.plate_number}"


class InvoiceItem(models.Model):
    """Items (spare parts) used in a garage invoice"""
    invoice = models.ForeignKey(GarageInvoice, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Optional: Link to original sale item if from stock
    from_sale_receipt = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        ordering = ['id']
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # Update invoice parts total
        invoice = self.invoice
        invoice.parts_total = sum(item.total_price for item in invoice.items.all())
        invoice.save()
    
    def __str__(self):
        return f"{self.item_name} x{self.quantity} - {self.invoice.invoice_number}"
