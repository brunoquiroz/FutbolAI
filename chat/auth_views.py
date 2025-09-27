from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse

def registro(request):
    """Vista para registro de usuarios"""
    if request.user.is_authenticated:
        return redirect('chat:chat')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}! Tu cuenta ha sido creada exitosamente.')
            return redirect('chat:chat')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = UserCreationForm()
    
    return render(request, 'chat/registro.html', {'form': form})

def login_view(request):
    """Vista para login de usuarios"""
    if request.user.is_authenticated:
        return redirect('chat:chat')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido de vuelta {username}!')
                return redirect('chat:chat')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'chat/login.html', {'form': form})

@login_required
def logout_view(request):
    """Vista para logout de usuarios"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('chat:login') 