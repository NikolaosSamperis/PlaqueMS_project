from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from .forms import UserRegistrationForm, UserLoginForm
from .models import User
from django.contrib import messages
from django.utils import timezone

    


def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful! Your account is pending approval.')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'login/register.html', {'form': form, 'registration_form': form})

def login_view(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_staff:
                login(request, user)
                return redirect('admin_dashboard')
            if not user.is_approved:
                messages.error(request, 'Your account is pending approval.')
                return redirect('login')
            login(request, user)
            return redirect('home')
    else:
        form = UserLoginForm()
    
    return render(request, 'login/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('home')

def is_admin(user):
    return user.is_staff

@user_passes_test(is_admin)
def admin_dashboard(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'login/admin_dashboard.html', {'users': users})

@user_passes_test(is_admin)
def approve_user(request, user_id):
    user = User.objects.get(id=user_id)
    user.is_approved = True
    user.approved_by = request.user
    user.approved_at = timezone.now()
    user.save()
    messages.success(request, f'User {user.email} has been approved.')
    return redirect('admin_dashboard')

@user_passes_test(is_admin)
def activate_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.is_active = True
        user.save()
        messages.success(request, f'User {user.email} has been activated.')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    return redirect('admin_dashboard')

@user_passes_test(is_admin)
def deactivate_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        if user.is_superuser:
            messages.error(request, 'Cannot deactivate a superuser account.')
        else:
            user.is_active = False
            user.save()
            messages.success(request, f'User {user.email} has been deactivated.')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    return redirect('admin_dashboard')

@user_passes_test(is_admin)
def delete_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        if user.is_superuser:
            messages.error(request, 'Cannot delete a superuser account.')
        else:
            user.delete()
            messages.success(request, f'User {user.email} has been deleted.')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
    return redirect('admin_dashboard') 