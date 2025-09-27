## Descripción General

FutbolAI es una aplicación web construida con Django que permite a usuarios autenticados hacer preguntas sobre fútbol en lenguaje natural. Internamente, el sistema:

- Genera consultas SQL sobre una base de datos MySQL con información de equipos, jornadas y partidos.
- Ejecuta esas consultas y presenta los resultados en una tabla.
- Genera una respuesta en lenguaje natural basada exclusivamente en los datos obtenidos.

<img width="1512" height="860" alt="Captura de pantalla 2025-09-27 a la(s) 2 11 08 a m" src="https://github.com/user-attachments/assets/49785b59-76e2-468c-aff8-63e4a6344963" />

---

## Tecnologías

- Backend:
  - Django (framework web de Python)
  - Módulo de autenticación de Django (registro, login, logout)
  - ORM de Django para modelos `Conversacion`, `Mensaje`, `PromptExtra`

- Lógica de IA y SQL:
  - SDK `openai` (cliente compatible con API OpenAI/compatibles)
  - Base de datos MySQL para los datos de fútbol
  - `mysql-connector-python` para ejecutar consultas SQL
  - `tabulate` para formatear resultados antes de generar respuestas

- Frontend:
  - Plantillas Django (`chat/templates/chat/`)
  - HTML/CSS/JavaScript vanilla
  - UI estilo chat con manejo de múltiples conversaciones
  - Enlaces a búsqueda en Google en resultados, con validación de términos excluidos

- Base de datos de desarrollo de Django:
  - `db.sqlite3` para la persistencia estándar de Django (usuarios, sesiones, conversaciones, mensajes)
  - MySQL externo para datos de fútbol (tablas: `equipos`, `jornadas`, `partidos`)

- Configuración/Entorno:
  - Variables de entorno leídas en `chat/chat_logic.py`: `API_BASE_URL`, `API_KEY`, `API_MODEL`

---

## Uso Básico

1. Inicia sesión o regístrate en `/chat/login/` o `/chat/registro/`.
2. Crea o selecciona una conversación en la UI.
3. Escribe preguntas como:
   - "Muestra los partidos del Barcelona en la Jornada 1."
   - "¿Qué equipos hay registrados?"
4. Revisa la respuesta y la tabla de resultados; usa los enlaces de búsqueda cuando aparezcan.
5. Gestiona tus conversaciones desde la barra lateral.
