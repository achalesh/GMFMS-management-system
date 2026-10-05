from django.db import migrations


def backfill(apps, schema_editor):
    Facilitator = apps.get_model("facilitators", "Facilitator")
    History = apps.get_model("facilitators", "FacilitatorStatusHistory")
    for f in Facilitator.objects.using(schema_editor.connection.alias).all().iterator():
        appointment = f.appointments.order_by("-created_at", "pk").first()
        if appointment:
            f.current_appointment = appointment
            f.save(update_fields=["current_appointment"])
            History.objects.create(facilitator=f, appointment=appointment, action="registry_import",
                previous_status="", new_status=f.status, changed_by=f.approved_by,
                reason="Existing approved identity imported into registry history; original approval timestamp retained on identity.")


class Migration(migrations.Migration):
    dependencies = [("facilitators", "0002_facilitator_current_appointment_facilitator_revision_and_more")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
