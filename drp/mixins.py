from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login

from drp.constants import RESPONSABLE_ACHAT_GROUP_NAME


def user_is_responsable_achat(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=RESPONSABLE_ACHAT_GROUP_NAME).exists()


class ResponsableAchatRequiredMixin(UserPassesTestMixin):
    """Accès réservé aux superusers et aux membres du groupe Responsable Achat."""

    raise_exception = True

    def handle_no_permission(self):
        # Avec raise_exception=True, AccessMixin enverrait 403 aux anonymes ; on redirige vers la connexion.
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        return super().handle_no_permission()

    def test_func(self):
        return user_is_responsable_achat(self.request.user)
