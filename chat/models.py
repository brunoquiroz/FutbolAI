from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Conversacion(models.Model):
    """Modelo para almacenar conversaciones"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversaciones', null=True, blank=True)
    titulo = models.CharField(max_length=200, default="Nueva conversación")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_ultima_actividad = models.DateTimeField(default=timezone.now)
    activa = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-fecha_ultima_actividad']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.titulo} - {self.fecha_creacion.strftime('%d/%m/%Y %H:%M')}"
    
    def actualizar_actividad(self):
        """Actualiza la fecha de última actividad"""
        self.fecha_ultima_actividad = timezone.now()
        self.save()

class Mensaje(models.Model):
    """Modelo para almacenar mensajes individuales"""
    TIPO_CHOICES = [
        ('usuario', 'Usuario'),
        ('bot', 'Bot'),
    ]
    
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    contenido = models.TextField()
    sql_generado = models.TextField(blank=True, null=True)
    resultados_json = models.JSONField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['fecha_creacion']
    
    def __str__(self):
        return f"{self.tipo}: {self.contenido[:50]}..."

class PromptExtra(models.Model):
    """Modelo para prompts adicionales asignados por el administrador a usuarios específicos"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prompts_extras')
    texto = models.TextField(help_text="Prompt adicional que se agregará al prompt original")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Prompt extra para {self.usuario.username}: {self.texto[:50]}..."
