from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime
from auths.models import User

@login_required(login_url='login')
def dashboard(request):
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from stock.models import Sale, NewSparePart, UsedSparePart, Component, Expenditure
    from django.db.models import Sum, F, DecimalField, Count
    from django.utils import timezone
    from decimal import Decimal
    from datetime import timedelta
    import calendar
    
    # Get current date
    now = timezone.now()
    today = now.date()
    current_month = now.month
    current_year = now.year
    current_month_name = now.strftime('%B')
    
    # Calculate today's sales
    today_sales_qs = Sale.objects.filter(created_at__date=today)
    today_sales_count = today_sales_qs.count()
    today_sales_amount = today_sales_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Calculate this month's sales
    month_sales_qs = Sale.objects.filter(
        created_at__year=current_year,
        created_at__month=current_month
    )
    month_sales_count = month_sales_qs.count()
    month_sales_amount = month_sales_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Calculate this year's sales
    year_sales_qs = Sale.objects.filter(created_at__year=current_year)
    year_sales_count = year_sales_qs.count()
    year_sales_amount = year_sales_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Calculate weekly sales and expenditure for current month
    # Get the number of days in current month
    days_in_month = calendar.monthrange(current_year, current_month)[1]
    
    # Divide month into 4 weeks
    weekly_sales = []
    weekly_expenditure = []
    
    for week in range(4):
        # Calculate week start and end dates
        week_start = week * 7 + 1
        week_end = min((week + 1) * 7, days_in_month)
        
        # Sales for this week
        week_sales = Sale.objects.filter(
            created_at__year=current_year,
            created_at__month=current_month,
            created_at__day__gte=week_start,
            created_at__day__lte=week_end
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        weekly_sales.append(float(week_sales))
        
        # Expenditure for this week
        week_exp = Expenditure.objects.filter(
            date__year=current_year,
            date__month=current_month,
            date__day__gte=week_start,
            date__day__lte=week_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        weekly_expenditure.append(float(week_exp))
    
    # Product statistics
    # Count active products
    new_parts_count = NewSparePart.objects.filter(is_active=True).count()
    used_parts_count = UsedSparePart.objects.filter(is_active=True).count()
    components_count = Component.objects.filter(is_active=True).count()
    total_products = new_parts_count + used_parts_count + components_count
    
    # Calculate total inventory value
    new_parts_value = NewSparePart.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_quantity') * F('unit_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    used_parts_value = UsedSparePart.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_quantity') * F('whole_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    components_value = Component.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_quantity') * F('unit_price'), output_field=DecimalField())
    )['total'] or Decimal('0.00')
    
    total_inventory_value = new_parts_value + used_parts_value + components_value
    
    context = {
        'user': request.user,
        'today_sales_count': today_sales_count,
        'today_sales_amount': today_sales_amount,
        'month_sales_count': month_sales_count,
        'month_sales_amount': month_sales_amount,
        'year_sales_count': year_sales_count,
        'year_sales_amount': year_sales_amount,
        'current_month': current_month_name,
        'weekly_sales': weekly_sales,
        'weekly_expenditure': weekly_expenditure,
        'total_products': total_products,
        'new_parts_count': new_parts_count,
        'used_parts_count': used_parts_count,
        'components_count': components_count,
        'total_inventory_value': total_inventory_value,
        'active_page': 'dashboard',
        # Widget data for template
        'today_sales': f"{today_sales_amount:,.0f}",
        'month_sales': f"{month_sales_amount:,.0f}",
        'year_sales': f"{year_sales_amount:,.0f}",
        'today_date': today,
        'current_year': current_year,
    }
    
    return render(request, 'manager_dashboard.html', context)

@login_required(login_url='login')
def staff_list(request):
    if request.user.role != 'manager':
        messages.error(request, 'Huna ruhusa ya kufikia ukurasa huu')
        return redirect('login')
    
    # Get all staff and stock users
    staff_users = User.objects.filter(role__in=['staff', 'stock']).order_by('-date_joined')
    
    context = {
        'user': request.user,
        'staff_users': staff_users,
        'active_page': 'staff'
    }
    
    return render(request, 'staff_list.html', context)

@login_required(login_url='login')
def staff_create(request):
    if request.user.role != 'manager':
        messages.error(request, 'Huna ruhusa ya kufikia ukurasa huu')
        return redirect('login')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        mobile_number = request.POST.get('mobile_number')
        
        # Validation
        if not all([username, password, role]):
            return JsonResponse({
                'success': False,
                'message': 'Tafadhali jaza sehemu zote muhimu'
            })
        
        if role not in ['staff', 'stock']:
            return JsonResponse({
                'success': False,
                'message': 'Chaguo la jukumu si sahihi'
            })
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'success': False,
                'message': 'Jina la mtumiaji tayari lipo'
            })
        
        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
                mobile_number=mobile_number
            )
            return JsonResponse({
                'success': True,
                'message': f'Mfanyakazi {username} ameongezwa kikamilifu'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Kosa limetokea: {str(e)}'
            })
    
    context = {
        'user': request.user,
        'active_page': 'staff'
    }
    return render(request, 'staff_form.html', context)

@login_required(login_url='login')
def staff_edit(request, user_id):
    if request.user.role != 'manager':
        messages.error(request, 'Huna ruhusa ya kufikia ukurasa huu')
        return redirect('login')
    
    staff_user = get_object_or_404(User, id=user_id)
    
    # Prevent editing manager accounts
    if staff_user.role == 'manager':
        messages.error(request, 'Huwezi kuhariri akaunti ya meneja')
        return redirect('manager:staff_list')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        role = request.POST.get('role')
        mobile_number = request.POST.get('mobile_number')
        password = request.POST.get('password')
        
        # Validation
        if not all([username, role]):
            return JsonResponse({
                'success': False,
                'message': 'Tafadhali jaza sehemu zote muhimu'
            })
        
        if role not in ['staff', 'stock']:
            return JsonResponse({
                'success': False,
                'message': 'Chaguo la jukumu si sahihi'
            })
        
        # Check if username exists (excluding current user)
        if User.objects.filter(username=username).exclude(id=user_id).exists():
            return JsonResponse({
                'success': False,
                'message': 'Jina la mtumiaji tayari lipo'
            })
        
        # Update user
        try:
            staff_user.username = username
            staff_user.email = email
            staff_user.role = role
            staff_user.mobile_number = mobile_number
            
            # Update password if provided
            if password:
                staff_user.set_password(password)
            
            staff_user.save()
            return JsonResponse({
                'success': True,
                'message': f'Taarifa za {username} zimesasishwa kikamilifu'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Kosa limetokea: {str(e)}'
            })
    
    context = {
        'user': request.user,
        'staff_user': staff_user,
        'active_page': 'staff',
        'is_edit': True
    }
    return render(request, 'staff_form.html', context)

@login_required(login_url='login')
def staff_toggle_active(request, user_id):
    if request.user.role != 'manager':
        messages.error(request, 'Huna ruhusa ya kufikia ukurasa huu')
        return redirect('login')
    
    staff_user = get_object_or_404(User, id=user_id)
    
    # Prevent disabling manager accounts
    if staff_user.role == 'manager':
        messages.error(request, 'Huwezi kuzima akaunti ya meneja')
        return redirect('manager:staff_list')
    
    # Toggle active status
    staff_user.is_active = not staff_user.is_active
    staff_user.save()
    
    status = 'amewashwa' if staff_user.is_active else 'amezimwa'
    messages.success(request, f'Akaunti ya {staff_user.username} {status} kikamilifu')
    
    return redirect('manager:staff_list')


# Read-only views for manager
@login_required(login_url='login')
def products(request):
    """Manager view for products (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from stock.models import NewSparePart, UsedSparePart, Component
    
    # Get all products with proper prefetching
    new_parts = NewSparePart.objects.filter(is_active=True).order_by('-created_at')
    used_parts = UsedSparePart.objects.filter(is_active=True).prefetch_related('components').order_by('-created_at')
    components = Component.objects.filter(is_active=True).order_by('-created_at')
    
    context = {
        'user': request.user,
        'active_page': 'products',
        'new_parts': new_parts,
        'used_parts': used_parts,
        'components': components,
        'is_manager': True,
    }
    
    return render(request, 'manager_products.html', context)


@login_required(login_url='login')
def all_sales(request):
    """Manager view for all sales (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from stock.models import Sale
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    # Get filter parameters
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')
    
    # Base queryset
    sales = Sale.objects.all().order_by('-created_at')
    
    # Apply date filters
    if from_date:
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d')
            sales = sales.filter(created_at__date__gte=from_date_obj.date())
        except ValueError:
            from_date = ''
    
    if to_date:
        try:
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d')
            sales = sales.filter(created_at__date__lte=to_date_obj.date())
        except ValueError:
            to_date = ''
    
    # Statistics
    total_sales = sales.count()
    total_amount = sales.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    context = {
        'user': request.user,
        'active_page': 'all_sales',
        'sales': sales[:200],  # Limit to 200 recent sales
        'total_sales': total_sales,
        'total_amount': total_amount,
        'from_date': from_date,
        'to_date': to_date,
        'is_manager': True,
    }
    
    return render(request, 'manager_all_sales.html', context)


@login_required(login_url='login')
def sale_details(request, sale_id):
    """Manager view for sale details (read-only)"""
    if request.user.role != 'manager':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    from stock.models import Sale
    from django.http import JsonResponse
    
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
def car_diagnosing(request):
    """Manager view for car diagnosing (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from staff.models import CarDiagnosis
    from django.db.models import Sum, Count
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    # Get month and year from URL parameters or use current date
    now = timezone.now()
    current_year = int(request.GET.get('year', now.year))
    current_month = int(request.GET.get('month', now.month))
    
    # Create a date object for the selected month
    selected_date = datetime(current_year, current_month, 1)
    current_month_name = selected_date.strftime('%B')
    
    # Get diagnoses for selected month
    month_diagnoses = CarDiagnosis.objects.filter(
        diagnosis_date__year=current_year,
        diagnosis_date__month=current_month
    ).order_by('-diagnosis_date', '-created_at')
    
    # Calculate statistics
    month_total_diagnoses = month_diagnoses.count()
    month_total_amount = month_diagnoses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'user': request.user,
        'active_page': 'car_diagnosing',
        'month_diagnoses': month_diagnoses,
        'month_total_diagnoses': month_total_diagnoses,
        'month_total_amount': month_total_amount,
        'current_month_name': current_month_name,
        'current_year': current_year,
        'current_month': current_month,
        'is_manager': True,
    }
    
    return render(request, 'manager_car_diagnosing.html', context)


@login_required(login_url='login')
def customer_debts(request):
    """Manager view for customer debts (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from stock.models import Sale, PaymentHistory
    from django.db.models import Sum
    from django.utils import timezone
    from datetime import datetime
    from decimal import Decimal
    
    # Get current month for payments calculation
    now = timezone.now()
    current_year = now.year
    current_month = now.month
    current_month_name = now.strftime('%B %Y')
    
    # Get active debts (unpaid)
    active_debts = Sale.objects.filter(
        sale_type='debt',
        is_paid=False
    ).order_by('-created_at')
    
    # Get completed debts (paid)
    completed_debts = Sale.objects.filter(
        sale_type='debt',
        is_paid=True
    ).order_by('-updated_at')[:50]  # Last 50 paid debts
    
    # Calculate statistics
    active_debts_count = active_debts.count()
    total_debt_amount = sum(debt.total_amount - debt.paid_amount for debt in active_debts)
    
    # Calculate payments received this month
    payments_this_month = PaymentHistory.objects.filter(
        payment_date__year=current_year,
        payment_date__month=current_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'user': request.user,
        'active_page': 'customer_debts',
        'active_debts': active_debts,
        'completed_debts': completed_debts,
        'active_debts_count': active_debts_count,
        'total_debt_amount': total_debt_amount,
        'payments_this_month': payments_this_month,
        'current_month': current_month_name,
        'is_manager': True,
    }
    
    return render(request, 'manager_customer_debts.html', context)


@login_required(login_url='login')
def expenditure(request):
    """Manager view for expenditure (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from stock.models import Sale, PaymentHistory, Expenditure
    from staff.models import CarDiagnosis, OpeningBalance
    from django.db.models import Sum
    from django.utils import timezone
    from datetime import datetime, date
    from decimal import Decimal
    
    # Get month and year from URL parameters or use current date
    now = timezone.now()
    selected_year = int(request.GET.get('year', now.year))
    selected_month = int(request.GET.get('month', now.month))
    
    # Create a date object for the selected month
    selected_date = datetime(selected_year, selected_month, 1)
    current_month = selected_date.strftime('%B %Y')
    
    # Get expenditures for selected month
    expenditures = Expenditure.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).order_by('-date', '-created_at')
    
    # Calculate total expenditure
    total_expenditure = expenditures.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenditure_count = expenditures.count()
    
    # Calculate revenue
    regular_sales_revenue = Sale.objects.filter(
        sale_type='regular',
        created_at__year=selected_year,
        created_at__month=selected_month
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    debt_payments_received = PaymentHistory.objects.filter(
        payment_date__year=selected_year,
        payment_date__month=selected_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    car_diagnosing_revenue = CarDiagnosis.objects.filter(
        diagnosis_date__year=selected_year,
        diagnosis_date__month=selected_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Opening balance
    month_date = date(selected_year, selected_month, 1)
    opening_balance_obj = OpeningBalance.objects.filter(month=month_date).first()
    opening_balance = opening_balance_obj.amount if opening_balance_obj else Decimal('0.00')
    
    # Total revenue
    total_revenue = regular_sales_revenue + debt_payments_received + car_diagnosing_revenue + opening_balance
    
    # Remaining amount
    remaining_amount = total_revenue - total_expenditure
    
    context = {
        'user': request.user,
        'active_page': 'expenditure',
        'expenditures': expenditures,
        'total_expenditure': total_expenditure,
        'expenditure_count': expenditure_count,
        'remaining_amount': remaining_amount,
        'current_month': current_month,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'is_manager': True,
    }
    
    return render(request, 'manager_expenditure.html', context)


@login_required(login_url='login')
def opening_balance(request):
    """Manager view for opening balance (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from staff.models import OpeningBalance
    from django.db.models import Sum
    
    # Get all opening balances
    all_balances = OpeningBalance.objects.all().order_by('-month')
    
    # Calculate statistics
    total_count = all_balances.count()
    total_amount = all_balances.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'user': request.user,
        'opening_balances': all_balances,
        'total_count': total_count,
        'total_amount': total_amount,
    }
    
    return render(request, 'manager_opening_balance.html', context)


@login_required(login_url='login')
def funga_hesabu(request):
    """Manager view for funga hesabu (read-only)"""
    if request.user.role != 'manager':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    from stock.models import Sale, PaymentHistory, Expenditure
    from staff.models import CarDiagnosis, OpeningBalance
    from django.utils import timezone
    from django.db.models import Sum, Count
    from datetime import datetime, date
    from decimal import Decimal
    
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
    debt_payments_current_month = PaymentHistory.objects.filter(
        payment_date__year=selected_year,
        payment_date__month=selected_month,
        sale__created_at__year=selected_year,
        sale__created_at__month=selected_month
    )
    debt_payments_count = debt_payments_current_month.count()
    debt_payments_amount = debt_payments_current_month.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Debt Payments from Previous Months' Debts
    debt_payments_from_old_debts = PaymentHistory.objects.filter(
        payment_date__year=selected_year,
        payment_date__month=selected_month
    ).exclude(
        sale__created_at__year=selected_year,
        sale__created_at__month=selected_month
    )
    debt_payments_from_old_count = debt_payments_from_old_debts.count()
    debt_payments_from_old_amount = debt_payments_from_old_debts.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Outstanding Debts
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
    
    # Total Revenue
    total_revenue = regular_sales_amount + debt_payments_amount + car_diagnosing_amount + opening_balance
    
    # Total Sales
    total_sales_amount = regular_sales_amount + debt_sales_amount
    total_sales_count = regular_sales_count + debt_sales_count
    
    # Remaining Amount
    remaining_amount = total_revenue - expenditure_amount
    
    context = {
        'user': request.user,
        'active_page': 'funga_hesabu',
        'current_month': current_month,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'remaining_amount': remaining_amount,
        'total_revenue': total_revenue,
        'opening_balance': opening_balance,
        'regular_sales_count': regular_sales_count,
        'regular_sales_amount': regular_sales_amount,
        'debt_sales_count': debt_sales_count,
        'debt_sales_amount': debt_sales_amount,
        'total_sales_count': total_sales_count,
        'total_sales_amount': total_sales_amount,
        'debt_payments_count': debt_payments_count,
        'debt_payments_amount': debt_payments_amount,
        'debt_payments_from_old_count': debt_payments_from_old_count,
        'debt_payments_from_old_amount': debt_payments_from_old_amount,
        'outstanding_debts_count': outstanding_debts_count,
        'outstanding_debts_amount': outstanding_debts_amount,
        'car_diagnosing_count': car_diagnosing_count,
        'car_diagnosing_amount': car_diagnosing_amount,
        'expenditure_count': expenditure_count,
        'expenditure_amount': expenditure_amount,
        'is_manager': True,
    }
    
    return render(request, 'manager_funga_hesabu.html', context)

@login_required(login_url='login')
def debt_details(request, sale_id):
    """Get detailed information about a debt sale including items and payment history"""
    if request.user.role != 'manager':
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
