from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

class CarDiagnosis(models.Model):
    customer_name = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    diagnosis_date = models.DateField()
    diagnosed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='car_diagnoses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Car Diagnosis"
        verbose_name_plural = "Car Diagnoses"
    
    def __str__(self):
        return f"{self.customer_name} - Tsh {self.amount} ({self.created_at.strftime('%Y-%m-%d')})"


class OpeningBalance(models.Model):
    month = models.DateField(help_text="First day of the month")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Opening balance amount for the month"
    )
    previous_month_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Balance carried forward from previous month"
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='opening_balances'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-month']
        unique_together = ['month']
        verbose_name = "Opening Balance"
        verbose_name_plural = "Opening Balances"

    def __str__(self):
        return f"{self.month.strftime('%B %Y')} - Tsh {self.amount}"
