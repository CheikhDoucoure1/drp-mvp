# Generated manually — traçabilité : ne plus supprimer en cascade les invitations.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("drp", "0004_rename_date_cloture_verbose"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invitation",
            name="fournisseur",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="invitations",
                to="drp.fournisseur",
            ),
        ),
    ]
