from django.apps import AppConfig


class P0AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "p0_app"
    verbose_name = "A+ Esthetic Production Safety"

    def ready(self):
        from . import ops_models  # noqa: F401
