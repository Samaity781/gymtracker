from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Ensure signals (e.g. profile auto-creation) are registered on startup
        import accounts.signals  # noqa: F401
