from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'
    
    def ready(self):
        """تسجيل signals عند تحميل التطبيق"""
        import projects.signals  # noqa
