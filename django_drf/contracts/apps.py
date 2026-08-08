from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contracts"

    def ready(self):
        # Register the custom-auth schema extension before drf-spectacular inspects API views.
        from . import schema  # noqa: F401
