"""A fresh install starts with three labels, so the first ticket can be sorted."""

from django.db import migrations

LABELS = [("Bug", "#EB5757"), ("Feature", "#BB87FC"), ("Improvement", "#4EA7FC")]


def seed(apps, schema_editor):
    TicketLabel = apps.get_model("dev_tickets", "TicketLabel")
    for name, color in LABELS:
        TicketLabel.objects.get_or_create(name=name, defaults={"color": color})


class Migration(migrations.Migration):
    dependencies = [("dev_tickets", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
