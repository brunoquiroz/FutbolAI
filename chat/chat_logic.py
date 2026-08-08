import openai
import os
import mysql.connector
from tabulate import tabulate
import re
import json
from datetime import date, datetime
from dotenv import load_dotenv
from .models import Conversacion, Mensaje, PromptExtra
from django.conf import settings

load_dotenv()

# Configuración de API: primero desde settings, luego variables de entorno y, por último, valores por defecto
API_BASE_URL = getattr(settings, 'API_BASE_URL', os.environ.get('API_BASE_URL', 'http://127.0.0.1:1337/v1'))
API_KEY = getattr(settings, 'API_KEY', os.environ.get('API_KEY'))
API_MODEL = getattr(settings, 'API_MODEL', os.environ.get('API_MODEL', 'DeepSeek-R1-0528-Qwen3-8B-IQ4_XS'))

if not API_KEY:
    raise RuntimeError(
        "API_KEY no está configurada. Defínela como variable de entorno o en settings.py."
    )

# CONFIGURACIÓN DE BASE DE DATOS: se toma exclusivamente de variables de entorno
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME', 'ligas'),
}

if not db_config['password']:
    raise RuntimeError(
        "DB_PASSWORD no está configurada. Defínela como variable de entorno."
    )

def convertir_a_json_serializable(obj):
    """Convierte objetos de la base de datos a formato JSON serializable"""
    import decimal
    
    if obj is None:
        return None
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convertir_a_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convertir_a_json_serializable(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool)):
        return obj
    else:
        # Para cualquier otro tipo, convertir a string
        print(f"Tipo no manejado: {type(obj)}, valor: {obj}")
        return str(obj)

def _sanitizar_salida_modelo(texto: str) -> str:
    """Elimina bloques de pensamiento <think>...</think> y recorta espacios.
    Esto evita exponer trazas internas del modelo al usuario o dentro del SQL.
    """
    try:
        if not isinstance(texto, str):
            return texto
        # Eliminar bloques <think> ... </think>
        texto = re.sub(r"<think>[\s\S]*?</think>", "", texto, flags=re.IGNORECASE)
        # También eliminar posibles marcadores residuales tipo <think>
        texto = re.sub(r"</?think>", "", texto, flags=re.IGNORECASE)
        return texto.strip()
    except Exception:
        return texto

# ESQUEMA PARA GENERACIÓN DE SQL
ESQUEMA_TABLAS = """
TABLAS DISPONIBLES:

equipos(id, nombre)
jornadas(id, nombre)
partidos(id, jornada_id, fecha, hora, equipo_local_id, equipo_visita_id, goles_local_1t, goles_visita_1t, goles_local_final, goles_visita_final)

RELACIONES:
- partidos.jornada_id → jornadas.id
- partidos.equipo_local_id → equipos.id
- partidos.equipo_visita_id → equipos.id

CONSULTAS BÁSICAS QUE FUNCIONAN:

1. Para ver todos los equipos:
   SELECT id, nombre FROM equipos;

2. Para ver todas las jornadas:
   SELECT id, nombre FROM jornadas;

3. Para ver todos los partidos con nombres de equipos:
   SELECT p.id, p.fecha, p.hora, 
          el.nombre as equipo_local, ev.nombre as equipo_visita,
          p.goles_local_final, p.goles_visita_final
   FROM partidos p
   JOIN equipos el ON p.equipo_local_id = el.id
   JOIN equipos ev ON p.equipo_visita_id = ev.id;

4. Para ver partidos de una jornada específica:
   SELECT p.id, p.fecha, p.hora, 
          el.nombre as equipo_local, ev.nombre as equipo_visita,
          p.goles_local_final, p.goles_visita_final
   FROM partidos p
   JOIN equipos el ON p.equipo_local_id = el.id
   JOIN equipos ev ON p.equipo_visita_id = ev.id
   JOIN jornadas j ON p.jornada_id = j.id
   WHERE j.nombre = 'Jornada 1';

5. Para buscar un equipo específico:
   SELECT id, nombre FROM equipos WHERE LOWER(nombre) LIKE LOWER('%barcelona%');

CONSULTAS AVANZADAS:

6. Para partidos entre dos equipos específicos (ejemplo: Barcelona vs Real Madrid):
   SELECT 
       j.nombre AS jornada,
       p.fecha,
       p.hora,
       el.nombre AS equipo_local,
       ev.nombre AS equipo_visita,
       IFNULL(p.goles_local_final, 0) AS goles_local,
       IFNULL(p.goles_visita_final, 0) AS goles_visita
   FROM 
       partidos p
   JOIN equipos el ON p.equipo_local_id = el.id
   JOIN equipos ev ON p.equipo_visita_id = ev.id
   JOIN jornadas j ON p.jornada_id = j.id
   WHERE 
       (
           (LOWER(el.nombre) LIKE '%barcelona%' AND LOWER(ev.nombre) LIKE '%real madrid%')
           OR
           (LOWER(el.nombre) LIKE '%real madrid%' AND LOWER(ev.nombre) LIKE '%barcelona%')
       )
   ORDER BY p.fecha DESC, p.hora DESC
   LIMIT 100;

7. Para estadísticas de un equipo específico:
   SELECT 
       e.nombre,
       COUNT(*) as total_partidos,
       SUM(CASE WHEN p.equipo_local_id = e.id THEN p.goles_local_final ELSE p.goles_visita_final END) as goles_favor,
       SUM(CASE WHEN p.equipo_local_id = e.id THEN p.goles_visita_final ELSE p.goles_local_final END) as goles_contra
   FROM equipos e
   LEFT JOIN partidos p ON (p.equipo_local_id = e.id OR p.equipo_visita_id = e.id)
   WHERE LOWER(e.nombre) LIKE LOWER('%barcelona%')
   GROUP BY e.id, e.nombre;

8. Para partidos con resultado específico (ejemplo: victorias por más de 2 goles):
   SELECT 
       j.nombre AS jornada,
       p.fecha,
       el.nombre AS equipo_local,
       ev.nombre AS equipo_visita,
       p.goles_local_final,
       p.goles_visita_final
   FROM partidos p
   JOIN equipos el ON p.equipo_local_id = el.id
   JOIN equipos ev ON p.equipo_visita_id = ev.id
   JOIN jornadas j ON p.jornada_id = j.id
   WHERE ABS(p.goles_local_final - p.goles_visita_final) > 2
   ORDER BY p.fecha DESC;

REGLAS PARA CONSULTAS:
1. La base de datos es MySQL.
2. Para búsquedas textuales, usa LIKE con LOWER().
3. SIEMPRE usa JOIN para obtener nombres de equipos desde IDs.
4. No generes instrucciones que modifiquen datos (INSERT, UPDATE, DELETE, CREATE).
5. Usa LIMIT 100 y ORDER BY cuando corresponda.
6. Prioriza claridad y agrupaciones cuando sea útil (por ejemplo: COUNT, AVG, MAX).
7. Usa IFNULL para prevenir valores nulos.
8. Considera el uso de alias para nombres de columnas.
9. Para partidos, SIEMPRE haz JOIN con equipos para mostrar nombres en lugar de IDs.
10. Usa LEFT JOIN cuando quieras incluir equipos sin partidos.
11. Si preguntan por equipos, usa la tabla equipos.
12. Si preguntan por partidos, usa la tabla partidos con JOINs a equipos.
13. Si preguntan por jornadas, usa la tabla jornadas.
14. Para partidos entre equipos específicos, usa el patrón de la consulta 6.
15. Para estadísticas de equipos, usa el patrón de la consulta 7.
"""

class ChatManager:
    def __init__(self, conversacion_id=None):
        self.conversacion_id = conversacion_id
        self.client = openai.OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
    
    def obtener_sql(self, pregunta, contexto, prompts_extra=None):
        prompt = f"""
Eres un experto en fútbol y solo respondes preguntas sobre futbol con solamente la informacion que tienes en las tablas SQL y tambien eres un experto en SQL. A partir de la siguiente estructura de tablas y reglas:

{ESQUEMA_TABLAS}

Y teniendo en cuenta la conversación anterior:
{contexto}

Genera una consulta SQL en MySQL que responda esta pregunta:
"{pregunta}"

INSTRUCCIONES ESPECÍFICAS:
- SIEMPRE usa JOIN para obtener nombres de equipos en lugar de mostrar IDs
- Para partidos, muestra los nombres de los equipos, no los IDs
- Usa alias claros para las tablas (p para partidos, e para equipos, j para jornadas)
- Si la pregunta es sobre equipos, usa la tabla equipos
- Si la pregunta es sobre partidos, usa la tabla partidos con JOINs a equipos
- Si la pregunta es sobre jornadas, usa la tabla jornadas
- Si preguntan por "todos los equipos", usa: SELECT id, nombre FROM equipos;
- Si preguntan por "todos los partidos", usa la consulta con JOINs a equipos
- Si preguntan por partidos entre equipos específicos, usa el patrón de la consulta 6
- Si preguntan por estadísticas de un equipo, usa el patrón de la consulta 7
- Si no hay datos específicos, usa las consultas básicas que funcionan
- Para búsquedas de equipos, usa LOWER() y LIKE para hacer búsquedas flexibles
- Para partidos entre dos equipos, considera ambos órdenes (local/visitante)
"""

        # Agregar prompts extra si existen
        if prompts_extra:
            prompt += "\n\nRESTRICCIONES ESPECÍFICAS QUE DEBES RESPETAR:\n"
            for i, prompt_extra in enumerate(prompts_extra, 1):
                prompt += f"{i}. {prompt_extra}\n"
            prompt += "\nIMPORTANTE: Si la pregunta del usuario viola alguna de estas restricciones, NO generes una consulta SQL. En su lugar, responde ÚNICAMENTE con: 'No puedo proporcionar información sobre este tema debido a restricciones específicas.'"

        prompt += "\n\nENTREGA ÚNICAMENTE LA CONSULTA SQL SIN COMENTARIOS, EXPLICACIONES NI TEXTO ADICIONAL. SOLO LA CONSULTA SQL."

        try:
            respuesta = self.client.chat.completions.create(
                model=API_MODEL,
                messages=[
                    {"role": "system", "content": "Eres un asistente experto en fútbol y base de datos MySQL. Genera consultas SQL precisas y útiles basándote en los ejemplos proporcionados, especialmente para consultas complejas entre equipos. Respeta siempre las restricciones especificadas. Responde ÚNICAMENTE con la consulta SQL, sin explicaciones ni texto adicional."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=5000
            )
            contenido = respuesta.choices[0].message.content
            contenido = _sanitizar_salida_modelo(contenido)
            return contenido.strip()
        except Exception as e:
            return f"Error al generar SQL: {str(e)}"

    def ejecutar_sql(self, sql):
        try:
            conn = mysql.connector.connect(**db_config)
            cur = conn.cursor(dictionary=True)
            cur.execute(sql)
            resultados = cur.fetchall()
            cur.close()
            conn.close()

            print(f"Resultados originales: {resultados}")
            print(f"Número de resultados: {len(resultados) if resultados else 0}")

            # Reemplazar None por 0 en los campos de goles
            campos_goles = [
                'goles_local', 'goles_visita',
                'goles_local_final', 'goles_visita_final',
                'goles_local_1t', 'goles_visita_1t'
            ]
            
            for row in resultados:
                for campo in campos_goles:
                    if campo in row:
                        valor_original = row[campo]
                        print(f"Campo {campo}: valor original = {valor_original}, tipo = {type(valor_original)}")
                        
                        # Convertir None, 'None', o valores vacíos a 0
                        if valor_original is None or valor_original == 'None' or valor_original == '':
                            row[campo] = 0
                            print(f"  -> Convertido a 0")
                        elif isinstance(valor_original, str) and valor_original.strip() == '':
                            row[campo] = 0
                            print(f"  -> Convertido a 0 (string vacío)")

            # Convertir resultados a formato JSON serializable
            resultados_serializables = convertir_a_json_serializable(resultados)
            print(f"Resultados serializables: {resultados_serializables}")

            return resultados_serializables
        except Exception as e:
            print(f"Error en ejecutar_sql: {e}")
            return f"Error al ejecutar la consulta: {e}"

    def generar_respuesta(self, resultados, pregunta, contexto):
        if isinstance(resultados, str) and resultados.startswith("Error"):
            return resultados
        
        prompt = f"""
Eres un analista de datos de fútbol. A continuación se muestra una tabla con los resultados de una consulta sobre partidos, equipos o jornadas.

Pregunta del usuario: "{pregunta}"

Resultados:
{tabulate(resultados, headers="keys", tablefmt="grid")}

Usa exclusivamente los datos entregados para responder a la pregunta en lenguaje natural. No inventes información adicional ni generalizes si los datos son insuficientes. Sé claro, directo y evita tecnicismos.

Si no hay resultados, explica amablemente que no se encontraron datos para esa consulta.
"""
        try:
            respuesta = self.client.chat.completions.create(
                model=API_MODEL,
                messages=[
                    {"role": "system", "content": "Responde preguntas sobre fútbol en lenguaje natural, usando solo datos reales entregados."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=5000
            )
            contenido = respuesta.choices[0].message.content
            contenido = _sanitizar_salida_modelo(contenido)
            return contenido.strip()
        except Exception as e:
            return f"Error al generar respuesta: {str(e)}"

    def procesar_mensaje(self, mensaje, conversacion_id=None, usuario=None):
        if not mensaje.strip():
            return {
                'error': 'Por favor, ingresa una pregunta válida.',
                'sql': '',
                'resultados': [],
                'respuesta': ''
            }

        # Obtener prompts extra del usuario si existe
        prompts_extra = []
        if usuario and usuario.is_authenticated:
            prompts_extra = [p.texto for p in PromptExtra.objects.filter(usuario=usuario)]

        # Obtener o crear conversación
        if conversacion_id:
            try:
                # Verificar que la conversación pertenece al usuario
                if usuario:
                    conversacion = Conversacion.objects.get(id=conversacion_id, usuario=usuario)
                else:
                    conversacion = Conversacion.objects.get(id=conversacion_id)
            except Conversacion.DoesNotExist:
                if usuario:
                    conversacion = Conversacion.objects.create(
                        usuario=usuario,
                        titulo=f"Conversación {mensaje[:30]}..."
                    )
                else:
                    conversacion = Conversacion.objects.create(titulo=f"Conversación {mensaje[:30]}...")
        else:
            if usuario:
                conversacion = Conversacion.objects.create(
                    usuario=usuario,
                    titulo=f"Conversación {mensaje[:30]}..."
                )
            else:
                conversacion = Conversacion.objects.create(titulo=f"Conversación {mensaje[:30]}...")

        if mensaje.lower() == 'nueva':
            # Crear nueva conversación
            if usuario:
                nueva_conversacion = Conversacion.objects.create(
                    usuario=usuario,
                    titulo="Nueva conversación"
                )
            else:
                nueva_conversacion = Conversacion.objects.create(titulo="Nueva conversación")
            return {
                'mensaje': 'Se ha iniciado una nueva conversación.',
                'sql': '',
                'resultados': [],
                'respuesta': '',
                'conversacion_id': nueva_conversacion.id
            }

        # Obtener contexto de los últimos 5 mensajes
        mensajes_anteriores = conversacion.mensajes.all().order_by('-fecha_creacion')[:5]
        contexto = "\n".join([f"{msg.tipo}: {msg.contenido}" for msg in reversed(mensajes_anteriores)])

        try:
            # Generar SQL
            sql = self.obtener_sql(mensaje, contexto, prompts_extra)
            sql = re.sub(r"```sql|```", "", sql).strip()

            # Verificar si el SQL es un mensaje de restricción
            if sql.startswith("No puedo proporcionar información"):
                # Guardar mensaje del usuario
                Mensaje.objects.create(
                    conversacion=conversacion,
                    tipo='usuario',
                    contenido=mensaje,
                    sql_generado='',
                    resultados_json=None
                )

                # Guardar respuesta del bot
                Mensaje.objects.create(
                    conversacion=conversacion,
                    tipo='bot',
                    contenido=sql,
                    sql_generado='',
                    resultados_json=None
                )

                # Actualizar actividad de la conversación
                conversacion.actualizar_actividad()

                return {
                    'sql': '',
                    'resultados': [],
                    'respuesta': sql,
                    'error': None,
                    'conversacion_id': conversacion.id
                }

            # Verificar si el generador falló y devolvió un error
            if isinstance(sql, str) and sql.lower().startswith("error"):
                # Guardar mensaje del usuario
                Mensaje.objects.create(
                    conversacion=conversacion,
                    tipo='usuario',
                    contenido=mensaje,
                    sql_generado='',
                    resultados_json=None
                )

                # Guardar respuesta del bot con el error
                Mensaje.objects.create(
                    conversacion=conversacion,
                    tipo='bot',
                    contenido=sql,
                    sql_generado='',
                    resultados_json=None
                )

                # Actualizar actividad de la conversación
                conversacion.actualizar_actividad()

                return {
                    'sql': '',
                    'resultados': [],
                    'respuesta': '',
                    'error': sql,
                    'conversacion_id': conversacion.id
                }

            # Ejecutar SQL
            resultados = self.ejecutar_sql(sql)

            # Generar respuesta con prompts extra
            respuesta = self.generar_respuesta_con_prompts_extra(resultados, mensaje, contexto, prompts_extra)

            # Convertir resultados a JSON serializable si es necesario
            resultados_para_guardar = resultados if isinstance(resultados, list) else None
            resultados_para_respuesta = convertir_a_json_serializable(resultados) if isinstance(resultados, list) else []

            # Guardar mensaje del usuario
            Mensaje.objects.create(
                conversacion=conversacion,
                tipo='usuario',
                contenido=mensaje,
                sql_generado=sql,
                resultados_json=resultados_para_guardar
            )

            # Guardar respuesta del bot
            Mensaje.objects.create(
                conversacion=conversacion,
                tipo='bot',
                contenido=respuesta,
                sql_generado=sql,
                resultados_json=resultados_para_guardar
            )

            # Actualizar actividad de la conversación
            conversacion.actualizar_actividad()

            return {
                'sql': sql,
                'resultados': resultados_para_respuesta,
                'respuesta': respuesta,
                'error': None,
                'conversacion_id': conversacion.id
            }

        except Exception as e:
            return {
                'error': f'Se produjo un error: {str(e)}',
                'sql': '',
                'resultados': [],
                'respuesta': '',
                'conversacion_id': conversacion.id
            }

    def generar_respuesta_con_prompts_extra(self, resultados, pregunta, contexto, prompts_extra):
        """Genera respuesta incluyendo prompts extra del usuario"""
        if isinstance(resultados, str) and resultados.startswith("Error"):
            return resultados
        
        # Construir prompt base
        prompt_base = f"""
Eres un analista de datos de fútbol. A continuación se muestra una tabla con los resultados de una consulta sobre partidos, equipos o jornadas.

Pregunta del usuario: "{pregunta}"

Resultados:
{tabulate(resultados, headers="keys", tablefmt="grid")}

Usa exclusivamente los datos entregados para responder a la pregunta en lenguaje natural. No inventes información adicional ni generalizes si los datos son insuficientes. Sé claro, directo y evita tecnicismos.

Si no hay resultados, explica amablemente que no se encontraron datos para esa consulta.
"""
        
        # Agregar prompts extra si existen
        if prompts_extra:
            prompt_base += "\n\nINSTRUCCIONES ADICIONALES ESPECÍFICAS PARA ESTE USUARIO:\n"
            for i, prompt in enumerate(prompts_extra, 1):
                prompt_base += f"{i}. {prompt}\n"
        
        try:
            respuesta = self.client.chat.completions.create(
                model=API_MODEL,
                messages=[
                    {"role": "system", "content": "Responde preguntas sobre fútbol en lenguaje natural, usando solo datos reales entregados."},
                    {"role": "user", "content": prompt_base}
                ],
                temperature=0.3,
                max_tokens=5000
            )
            contenido = respuesta.choices[0].message.content
            contenido = _sanitizar_salida_modelo(contenido)
            return contenido.strip()
        except Exception as e:
            return f"Error al generar respuesta: {str(e)}"

    def obtener_historial(self, conversacion_id=None):
        if conversacion_id:
            try:
                conversacion = Conversacion.objects.get(id=conversacion_id)
                return [f"{msg.tipo}: {msg.contenido}" for msg in conversacion.mensajes.all()]
            except Conversacion.DoesNotExist:
                return []
        return []

    def limpiar_historial(self, conversacion_id=None):
        if conversacion_id:
            try:
                conversacion = Conversacion.objects.get(id=conversacion_id)
                conversacion.mensajes.all().delete()
                return True
            except Conversacion.DoesNotExist:
                return False
        return False

    def eliminar_conversacion(self, conversacion_id):
        try:
            conversacion = Conversacion.objects.get(id=conversacion_id)
            conversacion.delete()
            return True
        except Conversacion.DoesNotExist:
            return False

    def obtener_conversaciones(self):
        return Conversacion.objects.filter(activa=True).order_by('-fecha_ultima_actividad')

    def obtener_conversacion(self, conversacion_id):
        try:
            return Conversacion.objects.get(id=conversacion_id)
        except Conversacion.DoesNotExist:
            return None 