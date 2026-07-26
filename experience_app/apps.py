from django.apps import AppConfig


class ExperienceAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "experience_app"
    verbose_name = "A+ Esthetic Erweiterungen"

    def ready(self):
        # The management catalog combines extension models with the core
        # integration registry. Register the core model in the view module
        # after Django has loaded both apps to avoid import-order problems.
        from platform_app.models import IntegrationConfig
        from . import views

        views.IntegrationConfig = IntegrationConfig
