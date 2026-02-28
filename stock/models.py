from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class NewSparePart(models.Model):
    part_number = models.CharField(max_length=100, blank=True, null=True, help_text="Optional part number")
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='new_parts')
    description = models.TextField(blank=True, null=True)
    
    # Pricing
    buying_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], help_text="Price at which the part was purchased")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], help_text="Price at which the part is sold")
    
    # Inventory tracking
    initial_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    current_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    sold_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    minimum_stock_level = models.IntegerField(validators=[MinValueValidator(0)], default=5, help_text="Alert when stock falls below this level")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['part_number']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        if self.part_number:
            return f"{self.part_number} - {self.name}"
        return self.name

    @property
    def is_low_stock(self):
        return self.current_quantity <= self.minimum_stock_level and self.current_quantity > 0

    @property
    def is_out_of_stock(self):
        return self.current_quantity == 0

    @property
    def total_value(self):
        return self.current_quantity * self.selling_price

    @property
    def total_buying_value(self):
        return self.current_quantity * self.buying_price

    @property
    def profit_margin(self):
        if self.buying_price > 0:
            return ((self.selling_price - self.buying_price) / self.buying_price) * 100
        return 0

    @property
    def added_stock(self):
        """Calculate total stock added since initial quantity"""
        total_added = StockHistory.objects.filter(
            product_type='new',
            product_id=self.id
        ).aggregate(total=models.Sum('quantity_added'))['total'] or 0
        return total_added

    def save(self, *args, **kwargs):
        # sold_quantity is now updated manually in sale creation
        super().save(*args, **kwargs)


class UsedSparePart(models.Model):
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    part_number = models.CharField(max_length=100, blank=True, null=True, help_text="Optional part number")
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='used_parts')
    description = models.TextField(blank=True, null=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    
    # Pricing - can be sold as whole or parts
    whole_buying_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], help_text="Buying price for the entire used part")
    whole_selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], help_text="Selling price for the entire used part")
    
    # Inventory tracking
    initial_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=1)
    current_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=1)
    sold_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    
    # Can be sold as whole or broken down into components
    can_be_broken_down = models.BooleanField(default=True, help_text="Can this part be sold in components?")
    is_broken_down = models.BooleanField(default=False, help_text="Has this been broken into components?")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['part_number']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        if self.part_number:
            return f"{self.part_number} - {self.name} (Used)"
        return f"{self.name} (Used)"

    @property
    def is_out_of_stock(self):
        # If part can be broken down, check component stock
        if self.can_be_broken_down:
            # Check if all components are sold
            has_components_in_stock = self.components.filter(current_quantity__gt=0).exists()
            if not has_components_in_stock:
                # All components are out of stock
                return True
        
        # For regular parts or if components are in stock, check current_quantity
        return self.current_quantity == 0

    @property
    def components_stock_status(self):
        """Debug property to show component stock status"""
        if not self.can_be_broken_down:
            return "Not breakdown-able"
        
        components_with_stock = self.components.filter(current_quantity__gt=0).count()
        total_components = self.components.count()
        
        if total_components == 0:
            return "No components"
        elif components_with_stock == 0:
            return f"All {total_components} components out of stock"
        else:
            return f"{components_with_stock}/{total_components} components in stock"

    @property
    def total_value(self):
        if self.is_broken_down:
            return sum(comp.total_value for comp in self.components.all())
        return self.current_quantity * self.whole_selling_price

    @property
    def total_buying_value(self):
        if self.is_broken_down:
            return sum(comp.total_buying_value for comp in self.components.all())
        return self.current_quantity * self.whole_buying_price

    @property
    def profit_margin(self):
        if self.whole_buying_price > 0:
            return ((self.whole_selling_price - self.whole_buying_price) / self.whole_buying_price) * 100
        return 0

    @property
    def added_stock(self):
        """Calculate total stock added since initial quantity"""
        total_added = StockHistory.objects.filter(
            product_type='used',
            product_id=self.id
        ).aggregate(total=models.Sum('quantity_added'))['total'] or 0
        return total_added

    def save(self, *args, **kwargs):
        # sold_quantity is now updated manually in sale creation
        super().save(*args, **kwargs)


class Component(models.Model):
    used_spare_part = models.ForeignKey(UsedSparePart, on_delete=models.CASCADE, related_name='components')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Pricing
    buying_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], help_text="Buying price for this component")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], help_text="Selling price for this component")
    
    # Inventory tracking
    initial_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=1)
    current_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=1)
    sold_quantity = models.IntegerField(validators=[MinValueValidator(0)], default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (from {self.used_spare_part.name})"

    @property
    def is_out_of_stock(self):
        return self.current_quantity == 0

    @property
    def total_value(self):
        return self.current_quantity * self.selling_price

    @property
    def total_buying_value(self):
        return self.current_quantity * self.buying_price

    @property
    def profit_margin(self):
        if self.buying_price > 0:
            return ((self.selling_price - self.buying_price) / self.buying_price) * 100
        return 0

    @property
    def added_stock(self):
        """Calculate total stock added since initial quantity"""
        total_added = StockHistory.objects.filter(
            product_type='component',
            product_id=self.id
        ).aggregate(total=models.Sum('quantity_added'))['total'] or 0
        return total_added

    def save(self, *args, **kwargs):
        # sold_quantity is now updated manually in sale creation
        super().save(*args, **kwargs)


class Customer(models.Model):
    name = models.CharField(max_length=200)
    mobile_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['mobile_number']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} - {self.mobile_number}"

    @property
    def total_debt(self):
        """Calculate total outstanding debt for this customer"""
        return self.sales.filter(sale_type='debt', is_paid=False).aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0.00')

    @property
    def total_purchases(self):
        """Calculate total purchase amount"""
        return self.sales.aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0.00')


class StockHistory(models.Model):
    """Track all stock additions for historical records"""
    PRODUCT_TYPES = [
        ('new', 'New Spare Part'),
        ('used', 'Used Spare Part'),
        ('component', 'Component'),
    ]
    
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)
    product_id = models.PositiveIntegerField()
    product_name = models.CharField(max_length=200)
    quantity_added = models.IntegerField(validators=[MinValueValidator(1)])
    previous_quantity = models.IntegerField(validators=[MinValueValidator(0)])
    new_quantity = models.IntegerField(validators=[MinValueValidator(0)])
    reason = models.CharField(max_length=200, default="Stock replenishment")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_type', 'product_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.product_name}: +{self.quantity_added} ({self.previous_quantity} → {self.new_quantity})"


class Sale(models.Model):
    SALE_TYPE_CHOICES = [
        ('regular', 'Regular Sale'),
        ('debt', 'Customer Debt'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('cash', 'Cash'),
        ('mobile', 'Mobile Money'),
        ('bank', 'Bank Transfer'),
    ]

    receipt_number = models.CharField(max_length=50, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='sales', null=True, blank=True)
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='regular')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='cash')
    
    # Financial details
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    
    # Debt tracking
    is_paid = models.BooleanField(default=True, help_text="For debt sales, tracks if payment is complete")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    due_date = models.DateField(null=True, blank=True, help_text="Due date for debt payment")
    
    # Metadata
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sales_created')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['sale_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Receipt #{self.receipt_number} - TSh {self.total_amount}"

    def save(self, *args, **kwargs):
        # Generate unique receipt number if not exists
        if not self.receipt_number:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.receipt_number = f"RCP-{timestamp}"
        
        # Calculate totals
        self.total_amount = self.subtotal - self.discount
        
        # Set is_paid based on sale_type and paid_amount
        if self.sale_type == 'regular':
            self.is_paid = True
            self.paid_amount = self.total_amount
        else:  # debt
            self.is_paid = self.paid_amount >= self.total_amount
        
        super().save(*args, **kwargs)

    @property
    def remaining_debt(self):
        """Calculate remaining debt amount"""
        if self.sale_type == 'debt':
            return max(Decimal('0.00'), self.total_amount - self.paid_amount)
        return Decimal('0.00')

    @property
    def items_count(self):
        """Count total items in this sale"""
        return self.items.count()


class SaleItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('new_part', 'New Spare Part'),
        ('used_part', 'Used Spare Part'),
        ('component', 'Component'),
    ]

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    
    # Foreign keys to different product types (only one will be set)
    new_spare_part = models.ForeignKey(NewSparePart, on_delete=models.PROTECT, null=True, blank=True, related_name='sale_items')
    used_spare_part = models.ForeignKey(UsedSparePart, on_delete=models.PROTECT, null=True, blank=True, related_name='sale_items')
    component = models.ForeignKey(Component, on_delete=models.PROTECT, null=True, blank=True, related_name='sale_items')
    
    # Sale details
    item_name = models.CharField(max_length=200, help_text="Stored for record keeping")
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    total_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.item_name} x{self.quantity} - TSh {self.total_price}"

    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.quantity * self.unit_price
        
        # Inventory is now updated manually in the create_sale view
        # No auto-update here to prevent double counting
        
        super().save(*args, **kwargs)

    @property
    def product(self):
        """Return the actual product object"""
        if self.item_type == 'new_part':
            return self.new_spare_part
        elif self.item_type == 'used_part':
            return self.used_spare_part
        elif self.item_type == 'component':
            return self.component
        return None


class Expenditure(models.Model):
    """Track branch expenditures"""
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    purpose = models.CharField(max_length=255, help_text="Purpose or description of expenditure")
    date = models.DateField(help_text="Date of expenditure")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='expenditures_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f"{self.purpose} - TSh {self.amount} ({self.date})"


class PaymentHistory(models.Model):
    """Track individual payments made on debt sales"""
    sale = models.ForeignKey('Sale', on_delete=models.CASCADE, related_name='payment_history')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    payment_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='payments_recorded')
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name_plural = "Payment Histories"
        indexes = [
            models.Index(fields=['payment_date']),
            models.Index(fields=['-payment_date']),
        ]
    
    def __str__(self):
        return f"Payment of TSh {self.amount} for {self.sale.receipt_number}"


class StockAuthorization(models.Model):
    """Track when staff authorizes stock release for a sale"""
    sale = models.OneToOneField('Sale', on_delete=models.CASCADE, related_name='stock_authorization')
    authorized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='stock_authorizations')
    authorized_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-authorized_at']
        verbose_name = "Stock Authorization"
        verbose_name_plural = "Stock Authorizations"
        indexes = [
            models.Index(fields=['authorized_at']),
            models.Index(fields=['-authorized_at']),
        ]
    
    def __str__(self):
        return f"Stock Authorization for {self.sale.receipt_number}"
