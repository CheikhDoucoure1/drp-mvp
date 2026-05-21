from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("drp", "0005_invitation_fournisseur_protect"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="proforma",
            name="score",
        ),
    ]
