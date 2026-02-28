from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def login_view(request):
    # If user is already authenticated, redirect to their dashboard
    if request.user.is_authenticated:
        return redirect_based_on_role(request.user)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect_based_on_role(user)
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'login.html')

def redirect_based_on_role(user):
    if user.role == 'manager':
        return redirect('manager:dashboard')
    elif user.role == 'staff':
        return redirect('staff:dashboard')
    elif user.role == 'stock':
        return redirect('stock:dashboard')
    elif user.role == 'garage':
        return redirect('garage:dashboard')
    else:
        return redirect('logout')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('login')
