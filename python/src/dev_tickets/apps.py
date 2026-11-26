from django.apps import AppConfig


class DevTicketsConfig(AppConfig):
    name = "dev_tickets"
    label = "dev_tickets"
    verbose_name = "Dev tickets"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import conf

        conf.check()
