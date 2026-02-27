from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse
from .models import NewSparePart, UsedSparePart, Component, Category, StockHistory

@login_required(login_url='login')
def dashboard(request):
    if request.user.role != 'stock':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    # Count new and used parts (excluding components)
    new_parts_count = NewSparePart.objects.filter(is_active=True).count()
    used_parts_count = UsedSparePart.objects.filter(is_active=True).count()
    
    # Total products (excluding components)
    total_products = new_parts_count + used_parts_count

    # Total stock value across all types
    new_value = NewSparePart.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_quantity') * F('unit_price'))
    )['total'] or 0

    used_value = UsedSparePart.objects.filter(
        is_active=True, is_broken_down=False
    ).aggregate(
        total=Sum(F('current_quantity') * F('whole_price'))
    )['total'] or 0

    component_value = Component.objects.filter(is_active=True).aggregate(
        total=Sum(F('current_quantity') * F('unit_price'))
    )['total'] or 0

    total_stock_value = new_value + used_value + component_value

    context = {
        'user': request.user,
        'total_products': total_products,
        'new_parts_count': new_parts_count,
        'used_parts_count': used_parts_count,
        'total_stock_value': total_stock_value,
    }
    
    return render(request, 'stock_dashboard.html', context)


# All Spare Parts (Combined View)
@login_required(login_url='login')
def all_spareparts(request):
    if request.user.role != 'stock':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    new_parts = NewSparePart.objects.all().order_by('-created_at')
    used_parts = UsedSparePart.objects.select_related('category').prefetch_related('components').order_by('-created_at')
    categories = Category.objects.all()
    
    context = {
        'new_parts': new_parts,
        'used_parts': used_parts,
        'categories': categories,
    }
    return render(request, 'all_spareparts.html', context)


# New Spare Parts Management (Redirect to all_spareparts)
@login_required(login_url='login')
def new_parts_list(request):
    return redirect('stock:all_spareparts')


@login_required(login_url='login')
def new_part_create(request):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method == 'POST':
        try:
            initial_qty = request.POST.get('initial_quantity')
            
            part = NewSparePart.objects.create(
                part_number=request.POST.get('part_number') or None,
                name=request.POST.get('name'),
                category=None,
                description=request.POST.get('description') or None,
                unit_price=request.POST.get('unit_price'),
                initial_quantity=initial_qty,
                current_quantity=initial_qty,
                minimum_stock_level=request.POST.get('minimum_stock_level', 5),
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Product added successfully!'})
            messages.success(request, 'Product added successfully!')
            return redirect('stock:all_spareparts')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Error: {str(e)}')
            return redirect('stock:all_spareparts')


@login_required(login_url='login')
def new_part_edit(request, pk):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    part = get_object_or_404(NewSparePart, pk=pk)
    
    if request.method == 'POST':
        try:
            part.part_number = request.POST.get('part_number') or None
            part.name = request.POST.get('name')
            part.description = request.POST.get('description') or None
            part.unit_price = request.POST.get('unit_price')
            part.minimum_stock_level = request.POST.get('minimum_stock_level', 5)
            part.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Product updated successfully!'})
            messages.success(request, 'Product updated successfully!')
            return redirect('stock:all_spareparts')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Error: {str(e)}')
            return redirect('stock:all_spareparts')


@login_required(login_url='login')
def new_part_delete(request, pk):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    part = get_object_or_404(NewSparePart, pk=pk)
    
    if request.method == 'POST':
        part.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Product deleted successfully!'})
        messages.success(request, 'Product deleted successfully!')
        return redirect('stock:all_spareparts')


# Used Spare Parts Management (Redirect to all_spareparts)
@login_required(login_url='login')
def used_parts_list(request):
    return redirect('stock:all_spareparts')


@login_required(login_url='login')
def used_part_create(request):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method == 'POST':
        try:
            initial_qty = request.POST.get('initial_quantity', 1)
            
            # Check if components are provided
            component_names = request.POST.getlist('component_name[]')
            can_breakdown = len(component_names) > 0
            
            part = UsedSparePart.objects.create(
                part_number=request.POST.get('part_number') or None,
                name=request.POST.get('name'),
                category=None,
                description=request.POST.get('description') or None,
                condition=request.POST.get('condition', 'good'),
                whole_price=request.POST.get('whole_price'),
                initial_quantity=initial_qty,
                current_quantity=initial_qty,
                can_be_broken_down=can_breakdown,
            )
            
            # Create components if provided
            if can_breakdown:
                component_prices = request.POST.getlist('component_price[]')
                component_quantities = request.POST.getlist('component_quantity[]')
                
                for i, name in enumerate(component_names):
                    if name.strip():
                        Component.objects.create(
                            used_spare_part=part,
                            name=name,
                            unit_price=component_prices[i] if i < len(component_prices) else 0,
                            initial_quantity=component_quantities[i] if i < len(component_quantities) else 1,
                            current_quantity=component_quantities[i] if i < len(component_quantities) else 1,
                        )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Used product added successfully!'})
            messages.success(request, 'Used product added successfully!')
            return redirect('stock:all_spareparts')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Error: {str(e)}')
            return redirect('stock:all_spareparts')


@login_required(login_url='login')
def used_part_edit(request, pk):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    part = get_object_or_404(UsedSparePart, pk=pk)
    
    if request.method == 'POST':
        try:
            part.part_number = request.POST.get('part_number') or None
            part.name = request.POST.get('name')
            part.description = request.POST.get('description') or None
            part.condition = request.POST.get('condition', 'good')
            part.whole_price = request.POST.get('whole_price')
            part.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Product updated successfully!'})
            messages.success(request, 'Product updated successfully!')
            return redirect('stock:all_spareparts')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Error: {str(e)}')
            return redirect('stock:all_spareparts')


@login_required(login_url='login')
def used_part_delete(request, pk):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    part = get_object_or_404(UsedSparePart, pk=pk)
    
    if request.method == 'POST':
        part.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Product deleted successfully!'})
        messages.success(request, 'Product deleted successfully!')
        return redirect('stock:all_spareparts')


# Component Management
@login_required(login_url='login')
def components_list(request, used_part_id):
    if request.user.role != 'stock':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    used_part = get_object_or_404(UsedSparePart, pk=used_part_id)
    components = Component.objects.filter(used_spare_part=used_part)
    
    context = {
        'used_part': used_part,
        'components': components,
    }
    return render(request, 'components_list.html', context)


@login_required(login_url='login')
def components_json(request, used_part_id):
    # Allow stock, staff, and manager users to access components
    if request.user.role not in ['stock', 'staff', 'manager']:
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    used_part = get_object_or_404(UsedSparePart, pk=used_part_id)
    components = Component.objects.filter(used_spare_part=used_part, is_active=True)
    
    components_data = [{
        'id': comp.id,
        'name': comp.name,
        'unit_price': float(comp.unit_price),
        'initial_quantity': comp.initial_quantity,
        'sold_quantity': comp.sold_quantity,
        'current_quantity': comp.current_quantity,
    } for comp in components]
    
    return JsonResponse({'success': True, 'components': components_data})


@login_required(login_url='login')
def component_create(request, used_part_id):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'Huna ruhusa'}, status=403)
    
    used_part = get_object_or_404(UsedSparePart, pk=used_part_id)
    
    if request.method == 'POST':
        try:
            component = Component.objects.create(
                used_spare_part=used_part,
                name=request.POST.get('name'),
                description=request.POST.get('description') or None,
                unit_price=request.POST.get('unit_price'),
                initial_quantity=request.POST.get('initial_quantity', 1),
                current_quantity=request.POST.get('current_quantity', 1),
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Sehemu imeongezwa!'})
            messages.success(request, 'Sehemu imeongezwa!')
            return redirect('stock:components_list', used_part_id=used_part_id)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Kosa: {str(e)}')
            return redirect('stock:components_list', used_part_id=used_part_id)


@login_required(login_url='login')
def component_edit(request, pk):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'Huna ruhusa'}, status=403)
    
    component = get_object_or_404(Component, pk=pk)
    
    if request.method == 'POST':
        try:
            component.name = request.POST.get('name')
            component.description = request.POST.get('description') or None
            component.unit_price = request.POST.get('unit_price')
            component.current_quantity = request.POST.get('current_quantity')
            component.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Sehemu imebadilishwa!'})
            messages.success(request, 'Sehemu imebadilishwa!')
            return redirect('stock:components_list', used_part_id=component.used_spare_part.id)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Kosa: {str(e)}')
            return redirect('stock:components_list', used_part_id=component.used_spare_part.id)


@login_required(login_url='login')
def component_delete(request, pk):
    if request.user.role != 'stock':
        return JsonResponse({'success': False, 'message': 'Huna ruhusa'}, status=403)
    
    component = get_object_or_404(Component, pk=pk)
    used_part_id = component.used_spare_part.id
    
    if request.method == 'POST':
        component.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Sehemu imefutwa!'})
        messages.success(request, 'Sehemu imefutwa!')
        return redirect('stock:components_list', used_part_id=used_part_id)


@login_required(login_url='login')
def add_stock(request, product_type, pk):
    """Add stock to a product"""
    if request.user.role not in ['stock', 'staff']:
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    try:
        # Parse JSON data
        import json
        data = json.loads(request.body)
        quantity = data.get('quantity', 0)
        
        if quantity <= 0:
            return JsonResponse({'success': False, 'message': 'Quantity must be greater than 0'})
        
        # Get the product based on type
        if product_type == 'new':
            product = get_object_or_404(NewSparePart, pk=pk)
        elif product_type == 'used':
            product = get_object_or_404(UsedSparePart, pk=pk)
        else:
            return JsonResponse({'success': False, 'message': 'Invalid product type'})
        
        # Update stock
        old_quantity = product.current_quantity
        product.current_quantity += quantity
        product.save()
        
        # Create stock history record
        StockHistory.objects.create(
            product_type=product_type,
            product_id=product.id,
            product_name=product.name,
            quantity_added=quantity,
            previous_quantity=old_quantity,
            new_quantity=product.current_quantity,
            added_by=request.user
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'Added {quantity} units to {product.name}. Stock: {old_quantity} → {product.current_quantity}'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
