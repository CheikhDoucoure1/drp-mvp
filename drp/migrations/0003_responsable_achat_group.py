from django.db import migrations


def create_responsable_achat_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Responsable Achat")


def delete_responsable_achat_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Responsable Achat").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0001_initial"),
        ("drp", "0002_drp_date_cloture"),
    ]

    operations = [
        migrations.RunPython(create_responsable_achat_group, delete_responsable_achat_group),
    ]
