from django.apps import AppConfig


class DevTicketsConfig(AppConfig):
    name = "dev_tickets"
    label = "dev_tickets"
    verbose_name = "Dev tickets"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.core.signals import request_started
        from django.db.models.signals import post_delete, post_save

        from . import conf, states
        from .models import TicketState, TrackerSettings

        conf.check()
        # Lanes and stored settings are cached for a request; any change clears them.
        request_started.connect(states.clear_cache, dispatch_uid="dev_tickets_states")
        request_started.connect(conf.clear_cache, dispatch_uid="dev_tickets_conf")
        for signal in (post_save, post_delete):
            signal.connect(states.clear_cache, sender=TicketState, dispatch_uid=f"dt_s_{signal}")
            signal.connect(conf.clear_cache, sender=TrackerSettings, dispatch_uid=f"dt_c_{signal}")
