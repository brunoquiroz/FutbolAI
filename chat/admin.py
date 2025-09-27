from django.contrib import admin
from django.utils.html import format_html
from .models import Conversacion, Mensaje, PromptExtra

@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'fecha_creacion', 'fecha_ultima_actividad', 'activa', 'num_mensajes']
    list_filter = ['activa', 'fecha_creacion', 'fecha_ultima_actividad']
    search_fields = ['titulo']
    readonly_fields = ['fecha_creacion', 'fecha_ultima_actividad']
    ordering = ['-fecha_ultima_actividad']
    
    def num_mensajes(self, obj):
        return obj.mensajes.count()
    num_mensajes.short_description = 'Número de mensajes'
    
    fieldsets = (
        ('Información básica', {
            'fields': ('titulo', 'activa')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_ultima_actividad'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ['conversacion', 'tipo', 'contenido_preview', 'fecha_creacion', 'tiene_sql', 'tiene_resultados']
    list_filter = ['tipo', 'fecha_creacion', 'conversacion']
    search_fields = ['contenido', 'conversacion__titulo']
    readonly_fields = ['fecha_creacion']
    ordering = ['-fecha_creacion']
    
    def contenido_preview(self, obj):
        return obj.contenido[:100] + "..." if len(obj.contenido) > 100 else obj.contenido
    contenido_preview.short_description = 'Contenido'
    
    def tiene_sql(self, obj):
        return bool(obj.sql_generado)
    tiene_sql.boolean = True
    tiene_sql.short_description = 'Tiene SQL'
    
    def tiene_resultados(self, obj):
        return bool(obj.resultados_json)
    tiene_resultados.boolean = True
    tiene_resultados.short_description = 'Tiene resultados'
    
    fieldsets = (
        ('Información básica', {
            'fields': ('conversacion', 'tipo', 'contenido')
        }),
        ('Datos técnicos', {
            'fields': ('sql_generado', 'resultados_json'),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('fecha_creacion',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('conversacion')

@admin.register(PromptExtra)
class PromptExtraAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'texto_preview', 'fecha_creacion']
    list_filter = ['usuario', 'fecha_creacion']
    search_fields = ['usuario__username', 'texto']
    ordering = ['-fecha_creacion']
    
    def texto_preview(self, obj):
        return obj.texto[:100] + "..." if len(obj.texto) > 100 else obj.texto
    texto_preview.short_description = 'Prompt'
    
    fieldsets = (
        ('Información básica', {
            'fields': ('usuario', 'texto')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('usuario')

# Configuración del sitio de administración
admin.site.site_header = "FutbolAI - Panel de Administración"
admin.site.site_title = "FutbolAI Admin"
admin.site.index_title = "Bienvenido al panel de administración de FutbolAI"
