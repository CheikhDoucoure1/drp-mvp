from datetime import timedelta

from django.db import migrations, models


def backfill_date_cloture_and_invitations(apps, schema_editor):
    DRP = apps.get_model("drp", "DRP")
    Invitation = apps.get_model("drp", "Invitation")
    for d in DRP.objects.filter(date_cloture__isnull=True):
        DRP.objects.filter(pk=d.pk).update(
            date_cloture=d.created_at + timedelta(days=14),
        )
    for inv in Invitation.objects.iterator():
        drp = DRP.objects.get(pk=inv.drp_id)
        Invitation.objects.filter(pk=inv.pk).update(expiration=drp.date_cloture)


class Migration(migrations.Migration):

    dependencies = [
        ("drp", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="drp",
            name="date_cloture",
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name="Date limite de réponse",
                help_text="Les fournisseurs ne peuvent plus soumettre de proforma après cette date.",
            ),
        ),
        migrations.RunPython(backfill_date_cloture_and_invitations, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="drp",
            name="date_cloture",
            field=models.DateTimeField(
                verbose_name="Date limite de réponse",
                help_text="Les fournisseurs ne peuvent plus soumettre de proforma après cette date.",
            ),
        ),
    ]
