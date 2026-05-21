from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def build_supplier_link(invitation, request=None) -> str:
    path = reverse("drp:supplier_proforma", kwargs={"token": str(invitation.token)})
    if request is not None:
        return request.build_absolute_uri(path)
    return f"{settings.SITE_PUBLIC_URL}{path}"


def send_invitation_email(invitation, request=None) -> None:
    """Envoie l’email d’invitation (texte brut, pas de HTML non fiable)."""
    link = build_supplier_link(invitation, request)
    subject = f"Demande de prix — {invitation.drp.titre}"
    body = (
        f"Bonjour,\n\n"
        f"Vous êtes invité(e) à répondre à une demande de prix (DRP) : {invitation.drp.titre}.\n\n"
        f"Lien sécurisé (unique, réponses attendues avant le {invitation.drp.date_cloture:%d/%m/%Y %H:%M}) :\n{link}\n\n"
        f"Merci de ne pas transférer ce lien.\n\n"
        f"Cordialement"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.fournisseur.email],
        fail_silently=False,
    )
