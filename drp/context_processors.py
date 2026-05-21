from drp.mixins import user_is_responsable_achat


def buyer_nav(request):
    return {
        "show_buyer_nav": user_is_responsable_achat(request.user)
        if getattr(request, "user", None) and request.user.is_authenticated
        else False,
    }
