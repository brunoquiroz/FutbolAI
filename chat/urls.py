from django.urls import path
from . import views
from . import auth_views

app_name = 'chat'

urlpatterns = [
    # Rutas de autenticación
    path('registro/', auth_views.registro, name='registro'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # Rutas del chat (protegidas)
    path('', views.chat_view, name='chat'),
    path('api/conversaciones/', views.conversaciones_list, name='conversaciones_list'),
    path('api/conversaciones/crear/', views.crear_conversacion, name='crear_conversacion'),
    path('api/conversaciones/<int:conversacion_id>/', views.conversacion_detail, name='conversacion_detail'),
    path('api/procesar/', views.procesar_mensaje, name='procesar_mensaje'),
    path('api/conversaciones/eliminar/', views.eliminar_conversacion, name='eliminar_conversacion'),
] 