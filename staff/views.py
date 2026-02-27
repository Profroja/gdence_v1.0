from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from datetime import datetime
import json

from stock.models import NewSparePart, UsedSparePart, Component, Customer, Sale, SaleItem
from .models import CarDiagnosis

@login_required(login_url='login')
def dashboard(request):
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from datetime import date
    
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    
    # Today's sales
    today_sales = Sale.objects.filter(created_at__date=today)
    today_sales_count = today_sales.count()
    today_total_amount = today_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    today_regular_amount = today_sales.filter(sale_type='regular').aggregate(total=Sum('total_amount'))['total'] or 0
    today_debt_amount = today_sales.filter(sale_type='debt').aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Monthly sales
    monthly_sales = Sale.objects.filter(created_at__date__gte=current_month_start)
    monthly_sales_count = monthly_sales.count()
    monthly_total_amount = monthly_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    monthly_regular_amount = monthly_sales.filter(sale_type='regular').aggregate(total=Sum('total_amount'))['total'] or 0
    monthly_debt_amount = monthly_sales.filter(sale_type='debt').aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'user': request.user,
        'active_page': 'dashboard',
        'today_sales_count': today_sales_count,
        'today_total_amount': today_total_amount,
        'today_regular_amount': today_regular_amount,
        'today_debt_amount': today_debt_amount,
        'monthly_sales_count': monthly_sales_count,
        'monthly_total_amount': monthly_total_amount,
        'monthly_regular_amount': monthly_regular_amount,
        'monthly_debt_amount': monthly_debt_amount,
    }
    return render(request, 'staff_dashboard.html', context)


@login_required(login_url='login')
def new_sale(request):
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    # Get all products for POS
    new_parts = NewSparePart.objects.filter(is_active=True)
    used_parts = UsedSparePart.objects.filter(is_active=True).prefetch_related('components')
    customers = Customer.objects.filter(is_active=True)
    
    context = {
        'user': request.user,
        'active_page': 'new_sale',
        'new_parts': new_parts,
        'used_parts': used_parts,
        'customers': customers,
    }
    return render(request, 'new_sale.html', context)


@login_required(login_url='login')
def create_sale(request):
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        
        # Extract sale data
        sale_type = data.get('sale_type', 'regular')
        payment_type = data.get('payment_type', 'cash')
        customer_name = data.get('customer_name')
        customer_mobile = data.get('customer_mobile')
        items = data.get('items', [])
        
        if not items:
            return JsonResponse({'success': False, 'message': 'No items in cart'}, status=400)
        
        # Start transaction
        with transaction.atomic():
            # Create or get customer if details provided
            customer = None
            if customer_name or customer_mobile:
                if customer_name and customer_mobile:
                    customer, created = Customer.objects.get_or_create(
                        mobile_number=customer_mobile,
                        defaults={'name': customer_name}
                    )
                elif customer_mobile:
                    customer, created = Customer.objects.get_or_create(
                        mobile_number=customer_mobile,
                        defaults={'name': 'Customer'}
                    )
            
            # Calculate totals
            subtotal = sum(item['unit_price'] * item['quantity'] for item in items)
            discount = data.get('discount', 0)
            amount_paid = data.get('amount_paid', 0)
            due_date = data.get('due_date')
            
            # For regular sales, paid_amount is full amount. For debt, use provided amount_paid
            if sale_type == 'regular':
                paid_amount = subtotal - discount
            else:
                paid_amount = amount_paid
            
            # Generate receipt number
            receipt_number = f"RCP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create sale
            sale = Sale.objects.create(
                receipt_number=receipt_number,
                sale_type=sale_type,
                payment_type=payment_type,
                customer=customer,
                subtotal=subtotal,
                discount=discount,
                paid_amount=paid_amount,
                due_date=due_date if sale_type == 'debt' else None,
                created_by=request.user
            )
            
            # Create sale items and update inventory
            for item_data in items:
                product_id = item_data['product_id']
                product_type = item_data['product_type']
                quantity = int(item_data['quantity'])  # Ensure quantity is integer
                unit_price = item_data['unit_price']
                
                # Get the product based on type and check stock
                product = None
                item_type = None
                sale_item_kwargs = {
                    'sale': sale,
                    'quantity': quantity,
                    'unit_price': unit_price,
                }
                
                if product_type == 'new':
                    product = NewSparePart.objects.get(id=product_id)
                    if product.current_quantity < quantity:
                        raise ValueError(f'Insufficient stock for {product.name}')
                    
                    item_type = 'new_part'
                    sale_item_kwargs['new_spare_part'] = product
                    sale_item_kwargs['item_type'] = item_type
                    sale_item_kwargs['item_name'] = product.name
                    
                    # Update inventory - update both current_quantity and sold_quantity
                    product.current_quantity -= quantity
                    product.sold_quantity += quantity
                    product.save()
                    
                elif product_type == 'used':
                    product = UsedSparePart.objects.get(id=product_id)
                    if product.current_quantity < quantity:
                        raise ValueError(f'Insufficient stock for {product.name}')
                    item_type = 'used_part'
                    sale_item_kwargs['used_spare_part'] = product
                    sale_item_kwargs['item_type'] = item_type
                    sale_item_kwargs['item_name'] = product.name
                    # Update inventory - update both current_quantity and sold_quantity
                    product.current_quantity -= quantity
                    product.sold_quantity += quantity
                    product.save()
                    
                elif product_type == 'component':
                    product = Component.objects.get(id=product_id)
                    if product.current_quantity < quantity:
                        raise ValueError(f'Insufficient stock for {product.name}')
                    item_type = 'component'
                    sale_item_kwargs['component'] = product
                    sale_item_kwargs['item_type'] = item_type
                    sale_item_kwargs['item_name'] = product.name
                    # Update inventory - update both current_quantity and sold_quantity
                    product.current_quantity -= quantity
                    product.sold_quantity += quantity
                    product.save()
                
                # Create sale item
                SaleItem.objects.create(**sale_item_kwargs)
            
            return JsonResponse({
                'success': True,
                'message': 'Sale completed successfully',
                'receipt_number': receipt_number,
                'sale_id': sale.id,
                'total_amount': float(sale.total_amount)
            })
    
    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@login_required(login_url='login')
def all_sales(request):
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    sale_type = request.GET.get('sale_type')
    payment_status = request.GET.get('payment_status')
    
    # Start with all sales
    sales = Sale.objects.all()
    
    # Apply filters
    if from_date:
        sales = sales.filter(created_at__date__gte=from_date)
    if to_date:
        sales = sales.filter(created_at__date__lte=to_date)
    if sale_type:
        sales = sales.filter(sale_type=sale_type)
    if payment_status:
        if payment_status == 'paid':
            sales = sales.filter(is_paid=True)
        elif payment_status == 'unpaid':
            sales = sales.filter(is_paid=False)
    
    # Calculate statistics based on filtered sales
    total_sales = sales.count()
    total_amount = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    regular_sales = sales.filter(sale_type='regular')
    regular_amount = regular_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    debt_sales_count = sales.filter(sale_type='debt').count()
    debt_amount = sales.filter(sale_type='debt').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    context = {
        'user': request.user,
        'active_page': 'sales_history',
        'sales': sales.order_by('-created_at'),
        'total_sales': total_sales,
        'total_amount': total_amount,
        'regular_amount': regular_amount,
        'debt_sales': debt_sales_count,
        'debt_amount': debt_amount,
        'from_date': from_date or '',
        'to_date': to_date or '',
        'sale_type': sale_type or '',
        'payment_status': payment_status or '',
    }
    return render(request, 'all_sales.html', context)


@login_required(login_url='login')
def sale_details(request, sale_id):
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    try:
        sale = Sale.objects.get(id=sale_id)
        
        # Get sale items
        items = []
        for item in sale.items.all():
            items.append({
                'name': item.item_name,
                'type': item.get_item_type_display(),
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_price': float(item.total_price),
            })
        
        sale_data = {
            'receipt_number': sale.receipt_number,
            'created_at': sale.created_at.strftime('%B %d, %Y %H:%M'),
            'customer': sale.customer.name if sale.customer else None,
            'sale_type': sale.get_sale_type_display(),
            'payment_type': sale.get_payment_type_display(),
            'is_paid': sale.is_paid,
            'subtotal': float(sale.subtotal),
            'discount': float(sale.discount),
            'total_amount': float(sale.total_amount),
            'paid_amount': float(sale.paid_amount),
            'items': items,
        }
        
        return JsonResponse({'success': True, 'sale': sale_data})
    
    except Sale.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Sale not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@login_required(login_url='login')
def products_view(request):
    """Read-only products view for staff users"""
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from stock.models import NewSparePart, UsedSparePart, Category
    
    new_parts = NewSparePart.objects.all().order_by('-created_at')
    used_parts = UsedSparePart.objects.select_related('category').prefetch_related('components').order_by('-created_at')
    categories = Category.objects.all()
    
    context = {
        'user': request.user,
        'active_page': 'products',
        'new_parts': new_parts,
        'used_parts': used_parts,
        'categories': categories,
    }
    return render(request, 'staff_products.html', context)


@login_required(login_url='login')
def record_payment(request, sale_id):
    """Record a payment for a debt sale"""
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
    
    from stock.models import Sale, PaymentHistory
    from decimal import Decimal
    import json
    
    try:
        data = json.loads(request.body)
        payment_amount = Decimal(str(data.get('amount', 0)))
        
        if payment_amount <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid payment amount'}, status=400)
        
        # Get the sale
        sale = Sale.objects.get(id=sale_id, sale_type='debt')
        
        # Check if payment exceeds remaining balance
        remaining = sale.total_amount - sale.paid_amount
        if payment_amount > remaining:
            return JsonResponse({
                'success': False, 
                'message': f'Payment amount exceeds remaining balance of TSh {remaining}'
            }, status=400)
        
        # Create payment history record
        PaymentHistory.objects.create(
            sale=sale,
            amount=payment_amount,
            created_by=request.user
        )
        
        # Update paid amount
        sale.paid_amount += payment_amount
        
        # Check if fully paid
        if sale.paid_amount >= sale.total_amount:
            sale.is_paid = True
        
        sale.save()
        
        # Calculate new balance
        new_balance = sale.total_amount - sale.paid_amount
        
        return JsonResponse({
            'success': True,
            'message': 'Payment recorded successfully',
            'new_balance': float(new_balance),
            'is_fully_paid': sale.is_paid
        })
        
    except Sale.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Debt sale not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@login_required(login_url='login')
def debt_details(request, sale_id):
    """Get detailed information about a debt sale including items and payment history"""
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    from stock.models import Sale, SaleItem, PaymentHistory
    from django.utils import timezone
    from decimal import Decimal
    
    try:
        # Get the sale
        sale = Sale.objects.select_related('customer').prefetch_related('items', 'payment_history').get(id=sale_id, sale_type='debt')
        
        # Get sale items
        items = []
        for item in sale.items.all():
            product_name = ''
            if item.new_spare_part:
                product_name = item.new_spare_part.name
            elif item.used_spare_part:
                product_name = item.used_spare_part.product_name
            
            items.append({
                'name': product_name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total': float(item.unit_price * item.quantity)
            })
        
        # Get payment history from PaymentHistory model
        payment_history = []
        running_balance = sale.total_amount
        
        # Get all payments ordered by date (oldest first for balance calculation)
        payments = sale.payment_history.all().order_by('payment_date')
        
        for payment in payments:
            running_balance -= payment.amount
            payment_history.append({
                'date': payment.payment_date.strftime('%b %d, %Y at %I:%M %p'),
                'amount': float(payment.amount),
                'balance_after': float(running_balance)
            })
        
        # Reverse to show newest first
        payment_history.reverse()
        
        # Format due date
        due_date_str = sale.due_date.strftime('%b %d, %Y') if sale.due_date else None
        
        return JsonResponse({
            'success': True,
            'receipt_number': sale.receipt_number,
            'customer_name': sale.customer.name if sale.customer else None,
            'customer_mobile': sale.customer.mobile_number if sale.customer else None,
            'due_date': due_date_str,
            'total_amount': float(sale.total_amount),
            'paid_amount': float(sale.paid_amount),
            'remaining_amount': float(sale.total_amount - sale.paid_amount),
            'items': items,
            'payment_history': payment_history
        })
        
    except Sale.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Debt sale not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@login_required(login_url='login')
def expenditure(request):
    """Branch expenditure management page"""
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from stock.models import Expenditure, Sale, PaymentHistory
    from django.utils import timezone
    from django.db.models import Sum
    from datetime import datetime
    from decimal import Decimal
    import calendar
    
    # Get month and year from URL parameters or use current date
    now = timezone.now()
    selected_year = int(request.GET.get('year', now.year))
    selected_month = int(request.GET.get('month', now.month))
    
    # Create a date object for the selected month
    selected_date = datetime(selected_year, selected_month, 1)
    current_month = selected_date.strftime('%B %Y')
    
    # Filter expenditures for selected month
    month_expenditures = Expenditure.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    )
    
    # Calculate total expenditure for the month
    total_expenditure = month_expenditures.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Get ALL active debts (unpaid, regardless of month created)
    all_active_debts = Sale.objects.filter(
        sale_type='debt',
        is_paid=False
    )
    total_debts = sum(debt.total_amount - debt.paid_amount for debt in all_active_debts)
    
    # Get regular sales for the selected month
    month_regular_sales = Sale.objects.filter(
        sale_type='regular',
        created_at__year=selected_year,
        created_at__month=selected_month
    )
    regular_sales_revenue = month_regular_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Get debt payments received in selected month (using PaymentHistory)
    month_debt_payments = PaymentHistory.objects.filter(
        payment_date__year=selected_year,
        payment_date__month=selected_month
    )
    debt_payments_received = month_debt_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Get car diagnosing revenue for selected month
    car_diagnosing_revenue = CarDiagnosis.objects.filter(
        diagnosis_date__year=selected_year,
        diagnosis_date__month=selected_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Get opening balance for selected month
    from .models import OpeningBalance
    from datetime import date
    month_date = date(selected_year, selected_month, 1)
    opening_balance_obj = OpeningBalance.objects.filter(month=month_date).first()
    opening_balance = opening_balance_obj.amount if opening_balance_obj else Decimal('0.00')
    
    # Total revenue for the month (cash actually received + opening balance)
    total_revenue = regular_sales_revenue + debt_payments_received + car_diagnosing_revenue + opening_balance
    
    # Calculate remaining amount: Total Revenue (including opening balance) - Expenditure
    remaining_amount = total_revenue - total_expenditure
    
    # Get expenditures for selected month for display (ordered by date)
    all_expenditures = Expenditure.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).order_by('-date', '-created_at')
    
    context = {
        'user': request.user,
        'active_page': 'expenditure',
        'current_month': current_month,
        'total_expenditure': total_expenditure,
        'total_debts': total_debts,
        'remaining_amount': remaining_amount,
        'expenditures': all_expenditures,
        'expenditure_count': month_expenditures.count(),
    }
    return render(request, 'expenditure.html', context)


@login_required(login_url='login')
def add_expenditure(request):
    """Add a new expenditure"""
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
    
    from stock.models import Expenditure
    from decimal import Decimal
    from datetime import datetime
    import json
    
    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount', 0)))
        purpose = data.get('purpose', '').strip()
        date_str = data.get('date', '')
        
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)
        
        if not purpose:
            return JsonResponse({'success': False, 'message': 'Purpose is required'}, status=400)
        
        if not date_str:
            return JsonResponse({'success': False, 'message': 'Date is required'}, status=400)
        
        # Parse date
        try:
            expenditure_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format'}, status=400)
        
        # Create expenditure
        expenditure = Expenditure.objects.create(
            amount=amount,
            purpose=purpose,
            date=expenditure_date,
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Expenditure added successfully',
            'expenditure': {
                'id': expenditure.id,
                'amount': float(expenditure.amount),
                'purpose': expenditure.purpose,
                'date': expenditure.date.strftime('%b %d, %Y')
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@login_required(login_url='login')
def customer_debts(request):
    """Customer debts management page"""
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from stock.models import Sale
    from django.utils import timezone
    from datetime import datetime
    
    # Get current month start and end
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get all debt sales
    all_debts = Sale.objects.filter(sale_type='debt').select_related('customer')
    
    # Active debts (not fully paid)
    active_debts = all_debts.filter(is_paid=False).order_by('-created_at')
    
    # Completed debts (fully paid)
    completed_debts = all_debts.filter(is_paid=True).order_by('-created_at')
    
    # Monthly statistics
    active_debts_count = active_debts.count()
    total_debt_amount = active_debts.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # Amount received this month (from any debt, even old ones)
    # This tracks payments made in the current month
    payments_this_month = all_debts.filter(
        updated_at__gte=month_start,
        paid_amount__gt=0
    ).aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
    
    context = {
        'user': request.user,
        'active_page': 'debts',
        'active_debts': active_debts,
        'completed_debts': completed_debts,
        'active_debts_count': active_debts_count,
        'total_debt_amount': total_debt_amount,
        'payments_this_month': payments_this_month,
        'current_month': now.strftime('%B %Y'),
    }
    return render(request, 'customer_debts.html', context)


@login_required(login_url='login')
def stock_status_api(request):
    """API endpoint to get current stock status for all products"""
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    try:
        products = []
        
        # Get new spare parts
        new_parts = NewSparePart.objects.filter(is_active=True)
        for part in new_parts:
            products.append({
                'id': part.id,
                'name': part.name,
                'type': 'new',
                'current_quantity': part.current_quantity,
                'minimum_stock_level': part.minimum_stock_level,
                'price': float(part.unit_price)
            })
        
        # Get used spare parts
        used_parts = UsedSparePart.objects.filter(is_active=True)
        for part in used_parts:
            products.append({
                'id': part.id,
                'name': part.name,
                'type': 'used',
                'current_quantity': part.current_quantity,
                'minimum_stock_level': 5,  # Default minimum for used parts
                'price': float(part.whole_price)
            })
        
        # Get components
        components = Component.objects.filter(is_active=True)
        for comp in components:
            products.append({
                'id': comp.id,
                'name': comp.name,
                'type': 'component',
                'current_quantity': comp.current_quantity,
                'minimum_stock_level': 2,  # Default minimum for components
                'price': float(comp.unit_price)
            })
        
        return JsonResponse({'success': True, 'products': products})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@login_required(login_url='login')
def car_diagnosing(request):
    """View for car diagnosing with monthly statistics"""
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from datetime import date
    from calendar import month_name
    
    # Get month and year from request or use current
    current_date = date.today()
    month = int(request.GET.get('month', current_date.month))
    year = int(request.GET.get('year', current_date.year))
    
    # Get diagnoses for the selected month
    month_diagnoses = CarDiagnosis.objects.filter(
        diagnosis_date__year=year,
        diagnosis_date__month=month
    ).order_by('-diagnosis_date', '-created_at')
    
    # Calculate monthly totals
    month_total_diagnoses = month_diagnoses.count()
    month_total_amount = month_diagnoses.aggregate(total=Sum('amount'))['total'] or 0
    
    # If AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        diagnoses_data = []
        for diagnosis in month_diagnoses:
            diagnoses_data.append({
                'customer_name': diagnosis.customer_name,
                'amount': float(diagnosis.amount),
                'diagnosis_date': diagnosis.diagnosis_date.strftime('%b %d, %Y'),
                'diagnosed_by': diagnosis.diagnosed_by.username if diagnosis.diagnosed_by else 'N/A',
                'notes': diagnosis.notes or ''
            })
        
        return JsonResponse({
            'total_diagnoses': month_total_diagnoses,
            'total_amount': float(month_total_amount),
            'diagnoses': diagnoses_data
        })
    
    # Regular page load
    context = {
        'user': request.user,
        'active_page': 'car_diagnosing',
        'current_month': month,
        'current_year': year,
        'current_month_name': month_name[month],
        'month_diagnoses': month_diagnoses,
        'month_total_diagnoses': month_total_diagnoses,
        'month_total_amount': month_total_amount,
    }
    
    return render(request, 'car_diagnosing.html', context)


@login_required(login_url='login')
def add_car_diagnosis(request):
    """Add a new car diagnosis record"""
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method == 'POST':
        try:
            from datetime import datetime
            
            customer_name = request.POST.get('customer_name', '').strip()
            amount = request.POST.get('amount', '').strip()
            diagnosis_date = request.POST.get('diagnosis_date', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            if not customer_name:
                return JsonResponse({'success': False, 'message': 'Customer name is required'})
            
            if not amount:
                return JsonResponse({'success': False, 'message': 'Amount is required'})
            
            if not diagnosis_date:
                return JsonResponse({'success': False, 'message': 'Diagnosis date is required'})
            
            # Create the diagnosis record
            diagnosis = CarDiagnosis.objects.create(
                customer_name=customer_name,
                amount=amount,
                diagnosis_date=diagnosis_date,
                notes=notes,
                diagnosed_by=request.user
            )
            
            messages.success(request, f'Car diagnosis for {customer_name} recorded successfully!')
            return JsonResponse({
                'success': True,
                'message': 'Diagnosis recorded successfully',
                'diagnosis_id': diagnosis.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required(login_url='login')
def opening_balance(request):
    """View for managing monthly opening balances"""
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from .models import OpeningBalance
    from django.db.models import Sum, Count
    
    # Get all opening balances
    all_balances = OpeningBalance.objects.all()
    
    # Calculate statistics
    total_count = all_balances.count()
    total_amount = all_balances.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'user': request.user,
        'active_page': 'opening_balance',
        'opening_balances': all_balances,
        'total_count': total_count,
        'total_amount': total_amount,
    }
    
    return render(request, 'staff_opening_balance.html', context)


@login_required(login_url='login')
def add_opening_balance(request):
    """Add a new opening balance record"""
    if request.user.role != 'staff':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method == 'POST':
        try:
            from .models import OpeningBalance
            from datetime import datetime
            from decimal import Decimal
            
            month_str = request.POST.get('month', '').strip()
            amount = request.POST.get('amount', '').strip()
            notes = request.POST.get('notes', '').strip()
            
            if not month_str:
                return JsonResponse({'success': False, 'message': 'Month is required'})
            
            if not amount:
                return JsonResponse({'success': False, 'message': 'Amount is required'})
            
            # Parse month (format: YYYY-MM)
            month_date = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
            
            # Check if opening balance already exists for this month
            if OpeningBalance.objects.filter(month=month_date).exists():
                return JsonResponse({'success': False, 'message': 'Opening balance for this month already exists'})
            
            # Get previous month's balance
            from dateutil.relativedelta import relativedelta
            previous_month = month_date - relativedelta(months=1)
            previous_balance_obj = OpeningBalance.objects.filter(month=previous_month).first()
            previous_balance = previous_balance_obj.amount if previous_balance_obj else Decimal('0.00')
            
            # Create the opening balance record
            opening_balance = OpeningBalance.objects.create(
                month=month_date,
                amount=Decimal(amount),
                previous_month_balance=previous_balance,
                notes=notes,
                added_by=request.user
            )
            
            messages.success(request, f'Opening balance for {month_date.strftime("%B %Y")} added successfully!')
            return JsonResponse({
                'success': True,
                'message': 'Opening balance added successfully',
                'balance_id': opening_balance.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required(login_url='login')
def funga_hesabu(request):
    """Monthly financial summary - Funga Hesabu"""
    if request.user.role != 'staff':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('logout')
    
    from stock.models import Sale, PaymentHistory, Expenditure
    from .models import CarDiagnosis, OpeningBalance
    from django.utils import timezone
    from django.db.models import Sum, Count
    from datetime import datetime, date
    from decimal import Decimal
    import calendar
    
    # Get month and year from URL parameters or use current date
    now = timezone.now()
    selected_year = int(request.GET.get('year', now.year))
    selected_month = int(request.GET.get('month', now.month))
    
    # Create a date object for the selected month
    selected_date = datetime(selected_year, selected_month, 1)
    current_month = selected_date.strftime('%B %Y')
    
    # Opening Balance
    month_date = date(selected_year, selected_month, 1)
    opening_balance_obj = OpeningBalance.objects.filter(month=month_date).first()
    opening_balance = opening_balance_obj.amount if opening_balance_obj else Decimal('0.00')
    
    # Regular Sales (Cash Sales)
    regular_sales = Sale.objects.filter(
        sale_type='regular',
        created_at__year=selected_year,
        created_at__month=selected_month
    )
    regular_sales_count = regular_sales.count()
    regular_sales_amount = regular_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Debt Sales Created
    debt_sales = Sale.objects.filter(
        sale_type='debt',
        created_at__year=selected_year,
        created_at__month=selected_month
    )
    debt_sales_count = debt_sales.count()
    debt_sales_amount = debt_sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Debt Payments from Current Month's Debts
    # Payments received this month from debts created this month
    debt_payments_current_month = PaymentHistory.objects.filter(
        payment_date__year=selected_year,
        payment_date__month=selected_month,
        sale__created_at__year=selected_year,
        sale__created_at__month=selected_month
    )
    debt_payments_count = debt_payments_current_month.count()
    debt_payments_amount = debt_payments_current_month.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Debt Payments from Previous Months' Debts
    # Payments received this month from debts created in previous months
    debt_payments_from_old_debts = PaymentHistory.objects.filter(
        payment_date__year=selected_year,
        payment_date__month=selected_month
    ).exclude(
        sale__created_at__year=selected_year,
        sale__created_at__month=selected_month
    )
    debt_payments_from_old_count = debt_payments_from_old_debts.count()
    debt_payments_from_old_amount = debt_payments_from_old_debts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Outstanding Debts (All unpaid debts regardless of month)
    outstanding_debts = Sale.objects.filter(sale_type='debt', is_paid=False)
    outstanding_debts_count = outstanding_debts.count()
    outstanding_debts_amount = sum(debt.total_amount - debt.paid_amount for debt in outstanding_debts)
    
    # Car Diagnosing Revenue
    car_diagnosing = CarDiagnosis.objects.filter(
        diagnosis_date__year=selected_year,
        diagnosis_date__month=selected_month
    )
    car_diagnosing_count = car_diagnosing.count()
    car_diagnosing_amount = car_diagnosing.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Expenditure
    expenditures = Expenditure.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    )
    expenditure_count = expenditures.count()
    expenditure_amount = expenditures.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Total Revenue (Cash received)
    total_revenue = regular_sales_amount + debt_payments_amount + car_diagnosing_amount + opening_balance
    
    # Total Sales (including debt sales created)
    total_sales_amount = regular_sales_amount + debt_sales_amount
    total_sales_count = regular_sales_count + debt_sales_count
    
    # Profit/Remaining Amount
    remaining_amount = total_revenue - expenditure_amount
    
    context = {
        'user': request.user,
        'active_page': 'funga_hesabu',
        'current_month': current_month,
        'selected_year': selected_year,
        'selected_month': selected_month,
        
        # Top Summary
        'remaining_amount': remaining_amount,
        'total_revenue': total_revenue,
        
        # Opening Balance
        'opening_balance': opening_balance,
        
        # Sales
        'regular_sales_count': regular_sales_count,
        'regular_sales_amount': regular_sales_amount,
        'debt_sales_count': debt_sales_count,
        'debt_sales_amount': debt_sales_amount,
        'total_sales_count': total_sales_count,
        'total_sales_amount': total_sales_amount,
        
        # Debt Payments
        'debt_payments_count': debt_payments_count,
        'debt_payments_amount': debt_payments_amount,
        
        # Debt Payments from Old Debts
        'debt_payments_from_old_count': debt_payments_from_old_count,
        'debt_payments_from_old_amount': debt_payments_from_old_amount,
        
        # Outstanding Debts
        'outstanding_debts_count': outstanding_debts_count,
        'outstanding_debts_amount': outstanding_debts_amount,
        
        # Car Diagnosing
        'car_diagnosing_count': car_diagnosing_count,
        'car_diagnosing_amount': car_diagnosing_amount,
        
        # Expenditure
        'expenditure_count': expenditure_count,
        'expenditure_amount': expenditure_amount,
    }
    
    return render(request, 'funga_hesabu.html', context)
