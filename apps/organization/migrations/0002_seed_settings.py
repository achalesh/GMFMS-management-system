from django.db import migrations


def seed_settings(apps, schema_editor):
    for model_name in ["OrganizationSetting", "SystemSetting"]:
        model = apps.get_model("organization", model_name)
        model.objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("organization", "0001_initial")]
    operations = [migrations.RunPython(seed_settings, migrations.RunPython.noop)]
