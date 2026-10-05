from django.db import migrations
from django.db.models import F


def preserve_times(apps, schema_editor):
    apps.get_model("facilitators", "FacilitatorAppointment").objects.using(schema_editor.connection.alias).update(approved_at=F("created_at"))


class Migration(migrations.Migration):
    dependencies = [("facilitators", "0004_facilitatorappointment_appointment_reference_and_more")]
    operations = [migrations.RunPython(preserve_times, migrations.RunPython.noop)]
