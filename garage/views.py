from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from datetime import datetime, timedelta
from .models import GarageInvoice, Vehicle, InvoiceItem


@login_required(login_url='login')
def dashboard(request):
    if request.user.role != 'garage':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    today = datetime.now().date()
    current_month_start = today.replace(day=1)
    current_year_start = today.replace(month=1, day=1)
    
    # Today's statistics
    today_invoices = GarageInvoice.objects.filter(created_at__date=today)
    today_services = today_invoices.count()
    today_labor = today_invoices.aggregate(total=Sum('labor_charge'))['total'] or 0
    today_parts = today_invoices.aggregate(total=Sum('parts_total'))['total'] or 0
    today_revenue = today_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Monthly statistics
    month_invoices = GarageInvoice.objects.filter(created_at__date__gte=current_month_start)
    month_services = month_invoices.count()
    month_labor = month_invoices.aggregate(total=Sum('labor_charge'))['total'] or 0
    month_parts = month_invoices.aggregate(total=Sum('parts_total'))['total'] or 0
    month_revenue = month_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Yearly statistics
    year_invoices = GarageInvoice.objects.filter(created_at__date__gte=current_year_start)
    year_services = year_invoices.count()
    year_labor = year_invoices.aggregate(total=Sum('labor_charge'))['total'] or 0
    year_parts = year_invoices.aggregate(total=Sum('parts_total'))['total'] or 0
    year_revenue = year_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Status breakdown
    pending_count = GarageInvoice.objects.filter(status='pending').count()
    in_progress_count = GarageInvoice.objects.filter(status='in_progress').count()
    completed_count = GarageInvoice.objects.filter(status='completed').count()
    paid_count = GarageInvoice.objects.filter(status='paid').count()
    
    # Total vehicles serviced
    total_vehicles = Vehicle.objects.count()
    
    # Recent invoices
    recent_invoices = GarageInvoice.objects.select_related('vehicle', 'created_by').order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        # Today
        'today_services': today_services,
        'today_labor': today_labor,
        'today_parts': today_parts,
        'today_revenue': today_revenue,
        # Month
        'month_services': month_services,
        'month_labor': month_labor,
        'month_parts': month_parts,
        'month_revenue': month_revenue,
        # Year
        'year_services': year_services,
        'year_labor': year_labor,
        'year_parts': year_parts,
        'year_revenue': year_revenue,
        # Status
        'pending_count': pending_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'paid_count': paid_count,
        # Other
        'total_vehicles': total_vehicles,
        'recent_invoices': recent_invoices,
        'today_date': today,
        'current_month': current_month_start.strftime('%B %Y'),
        'current_year': current_year_start.year,
    }
    
    return render(request, 'garage_dashboard.html', context)


@login_required(login_url='login')
def invoices(request):
    if request.user.role != 'garage':
        messages.error(request, 'You do not have permission to access this page')
        return redirect('login')
    
    today = datetime.now().date()
    current_month_start = today.replace(day=1)
    
    # Monthly invoices
    month_invoices = GarageInvoice.objects.filter(
        created_at__date__gte=current_month_start
    ).select_related('vehicle', 'created_by').order_by('-created_at')
    
    # Monthly statistics
    month_count = month_invoices.count()
    month_labor = month_invoices.aggregate(total=Sum('labor_charge'))['total'] or 0
    
    context = {
        'user': request.user,
        'invoices': month_invoices,
        'month_count': month_count,
        'month_labor': month_labor,
        'current_month': current_month_start.strftime('%B %Y'),
    }
    
    return render(request, 'garage_invoices.html', context)


@login_required(login_url='login')
def get_receipt(request, receipt_number):
    if request.user.role != 'garage':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    try:
        from stock.models import Sale
        
        sale = Sale.objects.filter(receipt_number=receipt_number).select_related('customer').first()
        
        if not sale:
            return JsonResponse({'success': False, 'message': 'Receipt not found'})
        
        # Get sale items
        items = []
        for item in sale.items.all():
            items.append({
                'name': item.item_name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_price': float(item.total_price),
            })
        
        receipt_data = {
            'receipt_number': sale.receipt_number,
            'total_amount': float(sale.total_amount),
            'is_paid': sale.is_paid,
            'customer': sale.customer.name if sale.customer else None,
            'items': items,
        }
        
        return JsonResponse({'success': True, 'receipt': receipt_data})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required(login_url='login')
def create_invoice(request):
    if request.user.role != 'garage':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        import json
        data = json.loads(request.body)
        
        # Get or create vehicle
        vehicle, created = Vehicle.objects.get_or_create(
            plate_number=data['plate_number'].upper(),
            defaults={
                'vehicle_model': data['vehicle_model'],
                'owner_name': data.get('owner_name', ''),
                'owner_phone': data.get('owner_phone', ''),
            }
        )
        
        # Update vehicle info if it already exists
        if not created:
            vehicle.vehicle_model = data['vehicle_model']
            vehicle.owner_name = data.get('owner_name', '')
            vehicle.owner_phone = data.get('owner_phone', '')
            vehicle.save()
        
        # Generate invoice number
        from datetime import datetime
        today = datetime.now()
        invoice_prefix = f"INV-{today.strftime('%Y%m%d')}"
        
        # Get last invoice number for today
        last_invoice = GarageInvoice.objects.filter(
            invoice_number__startswith=invoice_prefix
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            last_seq = int(last_invoice.invoice_number.split('-')[-1])
            new_seq = last_seq + 1
        else:
            new_seq = 1
        
        invoice_number = f"{invoice_prefix}-{new_seq:04d}"
        
        # Get receipt to calculate parts total (if receipt number provided)
        receipt_number = data.get('receipt_number', '').strip()
        parts_total = 0
        sale = None
        
        if receipt_number:
            from stock.models import Sale
            sale = Sale.objects.filter(receipt_number=receipt_number).first()
            parts_total = float(sale.total_amount) if sale else 0
        
        # Determine final status based on payment
        if data['payment_status'] == 'paid':
            final_status = 'paid'
        else:
            final_status = data['status']  # in_progress or completed
        
        # Create invoice
        invoice = GarageInvoice.objects.create(
            invoice_number=invoice_number,
            vehicle=vehicle,
            repair_description=data['service_description'],
            labor_charge=data['labor_charge'],
            sale_receipt_number=receipt_number if receipt_number else None,
            parts_total=parts_total,
            total_amount=parts_total + data['labor_charge'],
            status=final_status,
            created_by=request.user
        )
        
        # Create invoice items from sale items (only if receipt was provided)
        if sale:
            for sale_item in sale.items.all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    item_name=sale_item.item_name,
                    quantity=sale_item.quantity,
                    unit_price=sale_item.unit_price,
                    total_price=sale_item.total_price,
                    from_sale_receipt=receipt_number
                )
        
        return JsonResponse({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice_number': invoice_number,
            'invoice_id': invoice.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


from django.http import JsonResponse, HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from io import BytesIO


@login_required(login_url='login')
def invoice_details(request, invoice_id):
    if request.user.role not in ['garage', 'manager', 'staff']:
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    try:
        invoice = GarageInvoice.objects.select_related('vehicle').get(id=invoice_id)
        
        items = []
        for item in invoice.items.all():
            items.append({
                'name': item.item_name,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_price': float(item.total_price),
            })
        
        invoice_data = {
            'invoice_number': invoice.invoice_number,
            'vehicle_model': invoice.vehicle.vehicle_model,
            'plate_number': invoice.vehicle.plate_number,
            'owner_name': invoice.vehicle.owner_name,
            'owner_phone': invoice.vehicle.owner_phone,
            'repair_description': invoice.repair_description,
            'labor_charge': float(invoice.labor_charge),
            'parts_total': float(invoice.parts_total),
            'total_amount': float(invoice.total_amount),
            'status': invoice.get_status_display(),
            'items': items,
        }
        
        return JsonResponse({'success': True, 'invoice': invoice_data})
        
    except GarageInvoice.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invoice not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


@login_required(login_url='login')
def download_invoice(request, invoice_id):
    if request.user.role not in ['garage', 'manager', 'staff']:
        return HttpResponse('No permission', status=403)
    
    try:
        invoice = GarageInvoice.objects.select_related('vehicle').get(id=invoice_id)
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=(80*mm, 297*mm))
        
        y = 280*mm
        p.setFont("Courier-Bold", 10)
        p.drawCentredString(40*mm, y, "GARAGE SERVICE INVOICE")
        
        y -= 6*mm
        p.setFont("Courier", 7)
        p.drawCentredString(40*mm, y, "Gdence Autospare Parts")
        y -= 3*mm
        p.drawCentredString(40*mm, y, "Tel: +255 787 450 854")
        
        y -= 6*mm
        p.setDash(1, 2)
        p.line(5*mm, y, 75*mm, y)
        p.setDash()
        
        y -= 5*mm
        p.setFont("Courier-Bold", 8)
        p.drawString(5*mm, y, f"Invoice: {invoice.invoice_number}")
        
        y -= 4*mm
        p.setFont("Courier", 7)
        p.drawString(5*mm, y, f"Date: {invoice.created_at.strftime('%d/%m/%Y %H:%M')}")
        
        y -= 5*mm
        p.setDash(1, 2)
        p.line(5*mm, y, 75*mm, y)
        p.setDash()
        
        y -= 5*mm
        p.setFont("Courier-Bold", 8)
        p.drawString(5*mm, y, "VEHICLE INFORMATION")
        
        y -= 4*mm
        p.setFont("Courier", 7)
        p.drawString(5*mm, y, f"Model: {invoice.vehicle.vehicle_model}")
        
        y -= 3*mm
        p.drawString(5*mm, y, f"Plate: {invoice.vehicle.plate_number}")
        
        if invoice.vehicle.owner_name:
            y -= 3*mm
            p.drawString(5*mm, y, f"Owner: {invoice.vehicle.owner_name}")
        
        if invoice.vehicle.owner_phone:
            y -= 3*mm
            p.drawString(5*mm, y, f"Phone: {invoice.vehicle.owner_phone}")
        
        y -= 5*mm
        p.setDash(1, 2)
        p.line(5*mm, y, 75*mm, y)
        p.setDash()
        
        y -= 5*mm
        p.setFont("Courier-Bold", 8)
        p.drawString(5*mm, y, "SERVICE DESCRIPTION")
        
        y -= 4*mm
        p.setFont("Courier", 7)
        description_lines = invoice.repair_description.split('\n')
        for line in description_lines[:3]:
            if y < 30*mm:
                break
            p.drawString(5*mm, y, line[:45])
            y -= 3*mm
        
        y -= 4*mm
        p.setDash(1, 2)
        p.line(5*mm, y, 75*mm, y)
        p.setDash()
        
        y -= 5*mm
        p.setFont("Courier-Bold", 8)
        p.drawString(5*mm, y, "PARTS USED")
        
        y -= 4*mm
        p.setFont("Courier", 7)
        for item in invoice.items.all()[:10]:
            if y < 40*mm:
                break
            p.setFont("Courier-Bold", 7)
            p.drawString(5*mm, y, f"{item.item_name[:28]}")
            y -= 3*mm
            p.setFont("Courier", 6)
            p.drawString(7*mm, y, f"{item.quantity} x TSh {item.unit_price:,.0f}")
            p.drawRightString(75*mm, y, f"TSh {item.total_price:,.0f}")
            y -= 4*mm
        
        y -= 3*mm
        p.setDash(1, 2)
        p.line(5*mm, y, 75*mm, y)
        p.setDash()
        
        y -= 5*mm
        p.setFont("Courier", 7)
        p.drawString(5*mm, y, "Parts Total:")
        p.drawRightString(75*mm, y, f"TSh {invoice.parts_total:,.0f}")
        
        y -= 3*mm
        p.drawString(5*mm, y, "Labor Charges:")
        p.drawRightString(75*mm, y, f"TSh {invoice.labor_charge:,.0f}")
        
        y -= 5*mm
        p.setFont("Courier-Bold", 9)
        p.line(5*mm, y, 75*mm, y)
        y -= 4*mm
        p.drawString(5*mm, y, "TOTAL:")
        p.drawRightString(75*mm, y, f"TSh {invoice.total_amount:,.0f}")
        
        y -= 5*mm
        p.line(5*mm, y, 75*mm, y)
        y -= 1*mm
        p.line(5*mm, y, 75*mm, y)
        
        y -= 5*mm
        p.setFont("Courier", 7)
        p.drawString(5*mm, y, f"Status: {invoice.get_status_display()}")
        
        y -= 5*mm
        p.setDash(1, 2)
        p.line(5*mm, y, 75*mm, y)
        p.setDash()
        
        y -= 5*mm
        p.setFont("Courier", 7)
        p.drawCentredString(40*mm, y, "Thank you for your business!")
        y -= 3*mm
        p.drawCentredString(40*mm, y, "Please come again")
        y -= 4*mm
        p.setFont("Courier", 6)
        p.drawCentredString(40*mm, y, invoice.invoice_number)
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        
        return response
        
    except GarageInvoice.DoesNotExist:
        return HttpResponse('Invoice not found', status=404)
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)


@login_required(login_url='login')
def mark_completed(request, invoice_id):
    if request.user.role != 'garage':
        return JsonResponse({'success': False, 'message': 'No permission'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        import json
        data = json.loads(request.body)
        is_paid = data.get('is_paid', False)
        
        invoice = GarageInvoice.objects.get(id=invoice_id)
        
        if is_paid:
            invoice.status = 'paid'
        else:
            invoice.status = 'completed'
        
        invoice.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Invoice marked as {invoice.get_status_display()}'
        })
        
    except GarageInvoice.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invoice not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
