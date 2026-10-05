from django.db import migrations


def seed_roles(apps, schema_editor):
    role = apps.get_model("accounts", "Role")
    descriptions = {
        "SUPER_ADMIN": "Full system administration",
        "STATE_ADMIN": "State-wide facilitator administration",
        "DISTRICT_ADMIN": "Administration within assigned districts",
        "BLOCK_COORDINATOR": "Coordination within assigned blocks",
        "REVIEWER": "Review within assigned jurisdictions; cannot approve",
        "ID_CARD_OPERATOR": "Issue cards within assigned jurisdictions; cannot approve",
        "VIEWER": "Read-only access within assigned jurisdictions",
    }
    for code, description in descriptions.items():
        role.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={"description": description})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, migrations.RunPython.noop)]
