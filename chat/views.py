from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import json
from .chat_logic import ChatManager
from .models import Conversacion, Mensaje

# Instancia global del ChatManager
chat_manager = ChatManager()

@login_required
def chat_view(request):
    """Vista principal del chat - requiere autenticación"""
    return render(request, 'chat/chat.html')

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def procesar_mensaje(request):
    """API para procesar mensajes del chat"""
    try:
        data = json.loads(request.body)
        mensaje = data.get('mensaje', '').strip()
        conversacion_id = data.get('conversacion_id')
        
        # --- NUEVO: chequeo de términos excluidos ---
        terminos_excluidos = ['prohibido', 'ejemplo', 'test']  # Puedes luego cargar esto de la sesión o base de datos
        mensaje_lower = mensaje.lower()
        for t in terminos_excluidos:
            if t.lower() in mensaje_lower:
                return JsonResponse({
                    'error': None,
                    'sql': '',
                    'resultados': [],
                    'respuesta': f'El término "{t}" está excluido y no puedes usarlo en tus preguntas. Puedes modificar la lista de términos excluidos en el panel.',
                    'conversacion_id': conversacion_id
                })
        # --- FIN chequeo ---
        
        if not mensaje:
            return JsonResponse({
                'error': 'Por favor, ingresa una pregunta válida.',
                'sql': '',
                'resultados': [],
                'respuesta': '',
                'conversacion_id': conversacion_id
            })
        
        # Procesar el mensaje usando el ChatManager con el usuario actual
        resultado = chat_manager.procesar_mensaje(mensaje, conversacion_id, request.user)
        
        # Verificar que el resultado sea serializable
        try:
            json.dumps(resultado)
        except TypeError as json_error:
            print(f"Error de serialización JSON: {json_error}")
            print(f"Resultado problemático: {resultado}")
            return JsonResponse({
                'error': f'Error de serialización: {str(json_error)}',
                'sql': resultado.get('sql', ''),
                'resultados': [],
                'respuesta': resultado.get('respuesta', ''),
                'conversacion_id': resultado.get('conversacion_id')
            })
        
        return JsonResponse(resultado)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Error al procesar el mensaje JSON.',
            'sql': '',
            'resultados': [],
            'respuesta': ''
        })
    except Exception as e:
        print(f"Error general en procesar_mensaje: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Error interno del servidor: {str(e)}',
            'sql': '',
            'resultados': [],
            'respuesta': ''
        })

@require_http_methods(["GET"])
@login_required
def conversaciones_list(request):
    """API para obtener todas las conversaciones del usuario actual"""
    try:
        # Filtrar conversaciones por usuario
        conversaciones = Conversacion.objects.filter(usuario=request.user).order_by('-fecha_ultima_actividad')
        
        conversaciones_data = []
        for conv in conversaciones:
            conversaciones_data.append({
                'id': conv.id,
                'titulo': conv.titulo,
                'fecha_creacion': conv.fecha_creacion.isoformat(),
                'fecha_ultima_actividad': conv.fecha_ultima_actividad.isoformat(),
                'total_mensajes': conv.mensajes.count()
            })
        
        return JsonResponse({
            'conversaciones': conversaciones_data
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Error al obtener conversaciones: {str(e)}',
            'conversaciones': []
        })

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def crear_conversacion(request):
    """API para crear una nueva conversación para el usuario actual"""
    try:
        titulo = request.POST.get('titulo', 'Nueva conversación')
        conversacion = Conversacion.objects.create(
            usuario=request.user,
            titulo=titulo
        )
        return JsonResponse({
            'conversacion_id': conversacion.id,
            'titulo': conversacion.titulo,
            'fecha_creacion': conversacion.fecha_creacion.isoformat(),
            'mensaje': 'Conversación creada correctamente.'
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Error al crear conversación: {str(e)}'
        })

@require_http_methods(["GET"])
@login_required
def conversacion_detail(request, conversacion_id):
    """API para obtener una conversación específica del usuario actual"""
    try:
        # Verificar que la conversación pertenece al usuario
        conversacion = Conversacion.objects.filter(
            id=conversacion_id, 
            usuario=request.user
        ).first()
        
        if conversacion:
            mensajes_data = []
            for msg in conversacion.mensajes.all():
                mensajes_data.append({
                    'tipo': msg.tipo,
                    'contenido': msg.contenido,
                    'sql_generado': msg.sql_generado,
                    'resultados_json': msg.resultados_json,
                    'fecha_creacion': msg.fecha_creacion.isoformat()
                })
            
            return JsonResponse({
                'conversacion': {
                    'id': conversacion.id,
                    'titulo': conversacion.titulo,
                    'fecha_creacion': conversacion.fecha_creacion.isoformat(),
                    'fecha_ultima_actividad': conversacion.fecha_ultima_actividad.isoformat(),
                    'mensajes': mensajes_data
                }
            })
        else:
            return JsonResponse({
                'error': 'Conversación no encontrada o no tienes permisos para acceder a ella.'
            })
    except Exception as e:
        return JsonResponse({
            'error': f'Error al obtener conversación: {str(e)}'
        })

@require_http_methods(["GET"])
def obtener_historial(request):
    """API para obtener el historial del chat"""
    try:
        conversacion_id = request.GET.get('conversacion_id')
        chat_manager = ChatManager()
        historial = chat_manager.obtener_historial(conversacion_id)
        return JsonResponse({
            'historial': historial
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Error al obtener historial: {str(e)}',
            'historial': []
        })

@csrf_exempt
@require_http_methods(["POST"])
def limpiar_historial(request):
    """API para limpiar el historial del chat"""
    try:
        data = json.loads(request.body)
        conversacion_id = data.get('conversacion_id')
        chat_manager = ChatManager()
        success = chat_manager.limpiar_historial(conversacion_id)
        
        if success:
            return JsonResponse({
                'mensaje': 'Historial limpiado correctamente.'
            })
        else:
            return JsonResponse({
                'error': 'No se pudo limpiar el historial.'
            })
    except Exception as e:
        return JsonResponse({
            'error': f'Error al limpiar historial: {str(e)}'
        })

@csrf_exempt
@require_http_methods(["POST"])
def eliminar_conversacion(request):
    """API para eliminar una conversación"""
    try:
        data = json.loads(request.body)
        conversacion_id = data.get('conversacion_id')
        chat_manager = ChatManager()
        success = chat_manager.eliminar_conversacion(conversacion_id)
        
        if success:
            return JsonResponse({
                'mensaje': 'Conversación eliminada correctamente.'
            })
        else:
            return JsonResponse({
                'error': 'No se pudo eliminar la conversación.'
            })
    except Exception as e:
        return JsonResponse({
            'error': f'Error al eliminar conversación: {str(e)}'
        })
