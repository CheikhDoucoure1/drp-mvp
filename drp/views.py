from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_ratelimit.decorators import ratelimit

from drp.emailing import send_invitation_email
from drp.forms import (
    BuyerLoginForm,
    DRPChangeStatutForm,
    DomaineForm,
    DRPForm,
    FactureForm,
    FournisseurForm,
    ProformaResponseForm,
    SelectWinnerForm,
)
from drp.mixins import ResponsableAchatRequiredMixin, user_is_responsable_achat
from drp.models import Domaine, DRP, Facture, Fournisseur, Invitation, Proforma
from drp.services.analyse import generer_analyse_ia


def buyer_drp_queryset(user):
    qs = DRP.objects.all()
    if not user.is_superuser:
        qs = qs.filter(created_by=user)
    return qs


class BuyerLoginView(LoginView):
    """Ne redirige vers le tableau de bord que si l’utilisateur a accès acheteur (évite boucle login ↔ 403)."""

    template_name = "drp/login.html"
    form_class = BuyerLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and user_is_responsable_achat(request.user):
            return HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)


class BuyerLogoutView(View):
    """GET : page de confirmation ; POST : déconnexion (évite 405 sur /logout/ en navigation directe)."""

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        return render(request, "drp/logout_confirm.html")

    def post(self, request, *args, **kwargs):
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL)


class DomaineListView(LoginRequiredMixin, ResponsableAchatRequiredMixin, ListView):
    model = Domaine
    template_name = "drp/domaine_list.html"
    context_object_name = "domaines"
    queryset = Domaine.objects.all().order_by("nom")


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class DomaineCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = Domaine
    form_class = DomaineForm
    template_name = "drp/domaine_form.html"
    success_url = reverse_lazy("drp:domaine_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Créer un domaine"
        ctx["submit_label"] = "Créer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Domaine « {form.instance.nom} » créé.")
        return super().form_valid(form)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class DomaineUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = Domaine
    form_class = DomaineForm
    template_name = "drp/domaine_form.html"
    success_url = reverse_lazy("drp:domaine_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Modifier le domaine"
        ctx["submit_label"] = "Enregistrer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Domaine « {form.instance.nom} » mis à jour.")
        return super().form_valid(form)


class DomaineDeleteView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DeleteView):
    model = Domaine
    template_name = "drp/domaine_confirm_delete.html"
    success_url = reverse_lazy("drp:domaine_list")
    context_object_name = "domaine"

    def delete(self, request, *args, **kwargs):
        nom = str(self.get_object())
        result = super().delete(request, *args, **kwargs)
        messages.success(request, f"Le domaine « {nom} » a été supprimé.")
        return result


class FournisseurListView(LoginRequiredMixin, ResponsableAchatRequiredMixin, ListView):
    model = Fournisseur
    template_name = "drp/fournisseur_list.html"
    context_object_name = "fournisseurs"
    queryset = Fournisseur.objects.order_by("nom").prefetch_related("domaines")


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class FournisseurCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "drp/fournisseur_form.html"
    success_url = reverse_lazy("drp:fournisseur_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Nouveau fournisseur"
        ctx["submit_label"] = "Créer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Fournisseur « {form.instance.nom} » créé.")
        return super().form_valid(form)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class FournisseurUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "drp/fournisseur_form.html"
    success_url = reverse_lazy("drp:fournisseur_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Modifier le fournisseur"
        ctx["submit_label"] = "Enregistrer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Fournisseur « {form.instance.nom} » mis à jour.")
        return super().form_valid(form)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class FournisseurDesactiverView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DetailView):
    """Désactive le fournisseur (plus d’invitations futures) sans supprimer l’historique."""

    model = Fournisseur
    template_name = "drp/fournisseur_confirm_desactiver.html"
    context_object_name = "fournisseur"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.actif:
            messages.info(request, "Ce fournisseur est déjà désactivé.")
            return redirect("drp:fournisseur_list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.actif:
            messages.info(request, "Ce fournisseur est déjà désactivé.")
            return redirect("drp:fournisseur_list")
        nom = str(self.object)
        self.object.actif = False
        self.object.save(update_fields=["actif"])
        messages.success(
            request,
            f"Le fournisseur « {nom} » a été désactivé. Les invitations et proformas restent consultables sur les DRP concernés.",
        )
        return redirect("drp:fournisseur_list")


class DashboardView(LoginRequiredMixin, ResponsableAchatRequiredMixin, TemplateView):
    template_name = "drp/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = buyer_drp_queryset(self.request.user)
        ctx["total_drp"] = base_qs.count()
        ctx["drp_en_cours"] = base_qs.filter(statut=DRP.Statut.EN_COURS).count()
        ctx["drp_cloturees"] = base_qs.filter(statut=DRP.Statut.CLOTUREE).count()
        ctx["drp_annulees"] = base_qs.filter(statut=DRP.Statut.ANNULEE).count()
        ctx["drps"] = base_qs.annotate(nb_offres=Count("invitations__proforma"))[:50]
        return ctx


@method_decorator(ratelimit(key="user", rate="30/h", method="POST"), name="post")
class DRPCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = DRP
    form_class = DRPForm
    template_name = "drp/drp_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form_title", "Créer une DRP")
        ctx.setdefault("page_title", "Nouvelle DRP")
        ctx.setdefault("submit_label", "Enregistrer et inviter")
        ctx["cancel_href"] = reverse("drp:dashboard")
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            form.save_m2m()

            domaines_ids = list(self.object.domaines.values_list("pk", flat=True))
            fournisseurs = Fournisseur.objects.filter(actif=True, domaines__in=domaines_ids).distinct()
            expiration = self.object.date_cloture
            envoyes = 0
            for f in fournisseurs:
                inv, created = Invitation.objects.get_or_create(
                    fournisseur=f,
                    drp=self.object,
                    defaults={
                        "expiration": expiration,
                        "statut": Invitation.Statut.ENVOYEE,
                    },
                )
                if created:
                    try:
                        send_invitation_email(inv, self.request)
                        envoyes += 1
                    except Exception as exc:
                        messages.warning(
                            self.request,
                            f"L’invitation pour {f.nom} a été créée mais l’email n’a pas pu être envoyé ({exc}).",
                        )
            if not fournisseurs.exists():
                messages.warning(
                    self.request,
                    "Aucun fournisseur actif ne correspond aux domaines sélectionnés. Aucune invitation créée.",
                )
            elif envoyes:
                messages.success(
                    self.request,
                    f"DRP créée. {envoyes} invitation(s) envoyée(s) par email.",
                )
        return redirect("drp:dashboard")


@method_decorator(ratelimit(key="user", rate="30/h", method="POST"), name="post")
class DRPUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = DRP
    form_class = DRPForm
    template_name = "drp/drp_form.html"
    context_object_name = "drp"

    def get_queryset(self):
        return buyer_drp_queryset(self.request.user).filter(statut=DRP.Statut.EN_COURS)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "Modifier la DRP"
        ctx["page_title"] = "Modifier la DRP"
        ctx["submit_label"] = "Enregistrer les modifications"
        ctx["cancel_href"] = reverse("drp:drp_detail", kwargs={"pk": self.object.pk})
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            Invitation.objects.filter(drp=self.object).update(expiration=self.object.date_cloture)
        messages.success(self.request, "La DRP a été mise à jour.")
        return redirect("drp:drp_detail", pk=self.object.pk)


class DRPDetailView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DetailView):
    model = DRP
    template_name = "drp/drp_detail.html"
    context_object_name = "drp"

    def get_queryset(self):
        return buyer_drp_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        drp = self.object
        invitations = (
            drp.invitations.select_related("fournisseur")
            .prefetch_related("proforma")
            .order_by("fournisseur__nom")
        )
        ctx["invitations"] = invitations
        proformas = list(
            Proforma.objects.filter(invitation__drp=drp)
            .select_related("invitation", "invitation__fournisseur")
            .order_by("prix", "delai_jours", "pk")
        )
        ctx["proformas"] = proformas
        ctx["select_form"] = SelectWinnerForm(drp=drp)
        ctx["statut_form"] = DRPChangeStatutForm(drp=drp)
        ctx["limite_depassee"] = drp.est_limite_reponses_depassee()
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "change_statut":
            form = DRPChangeStatutForm(request.POST, drp=self.object)
            if form.is_valid():
                new_statut = form.cleaned_data["statut"]
                self.object.statut = new_statut
                update_fields = ["statut"]
                if new_statut == DRP.Statut.CLOTUREE:
                    # Clôture manuelle : pas de fournisseur retenu par ce flux
                    self.object.selected_invitation = None
                    update_fields.append("selected_invitation")
                elif new_statut in (DRP.Statut.EN_COURS, DRP.Statut.ANNULEE):
                    self.object.selected_invitation = None
                    update_fields.append("selected_invitation")
                self.object.save(update_fields=update_fields)
                messages.success(
                    request,
                    f"Statut mis à jour : « {self.object.get_statut_display()} ».",
                )
            else:
                err = next(iter(form.errors.values()), None)
                messages.error(
                    request,
                    err[0] if err else "Impossible de mettre à jour le statut.",
                )
            return redirect("drp:drp_detail", pk=self.object.pk)

        if action == "select_winner":
            if self.object.statut != DRP.Statut.EN_COURS:
                messages.error(request, "Impossible de retenir un fournisseur : la DRP n’est pas en cours.")
                return redirect("drp:drp_detail", pk=self.object.pk)
            form = SelectWinnerForm(request.POST, drp=self.object)
            if form.is_valid():
                inv = form.cleaned_data["invitation"]
                self.object.selected_invitation = inv
                self.object.statut = DRP.Statut.CLOTUREE
                self.object.save(update_fields=["selected_invitation", "statut"])
                messages.success(
                    request,
                    f"Fournisseur retenu : {inv.fournisseur.nom}. La DRP est clôturée.",
                )
            else:
                messages.error(request, "Choix invalide. Veuillez sélectionner une offre existante.")
            return redirect("drp:drp_detail", pk=self.object.pk)

        messages.error(request, "Action non reconnue.")
        return redirect("drp:drp_detail", pk=self.object.pk)


class DRPDeleteView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DeleteView):
    model = DRP
    template_name = "drp/drp_confirm_delete.html"
    success_url = reverse_lazy("drp:dashboard")
    context_object_name = "drp"

    def get_queryset(self):
        return buyer_drp_queryset(self.request.user).filter(
            statut__in=[DRP.Statut.EN_COURS, DRP.Statut.ANNULEE],
        )

    def delete(self, request, *args, **kwargs):
        messages.success(request, "La DRP a été supprimée.")
        return super().delete(request, *args, **kwargs)


@method_decorator(ratelimit(key="user", rate="30/h", method="POST"), name="post")
class FactureCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, View):
    """Saisie de la facture réelle pour un fournisseur retenu sur une DRP clôturée."""

    template_name = "drp/facture_form.html"

    def _get_invitation(self, drp_pk):
        drp = get_object_or_404(buyer_drp_queryset(self.request.user), pk=drp_pk)
        if drp.statut != DRP.Statut.CLOTUREE or not drp.selected_invitation:
            raise Http404
        return drp.selected_invitation

    def get(self, request, drp_pk, *args, **kwargs):
        invitation = self._get_invitation(drp_pk)
        try:
            facture_existante = invitation.facture
        except Facture.DoesNotExist:
            facture_existante = None
        form = FactureForm(instance=facture_existante)
        return render(request, self.template_name, {
            "form": form,
            "invitation": invitation,
            "drp": invitation.drp,
            "facture_existante": facture_existante,
        })

    def post(self, request, drp_pk, *args, **kwargs):
        invitation = self._get_invitation(drp_pk)
        try:
            instance = invitation.facture
        except Facture.DoesNotExist:
            instance = None
        form = FactureForm(request.POST, instance=instance)
        if form.is_valid():
            facture = form.save(commit=False)
            facture.invitation = invitation
            facture.created_by = request.user
            facture.save()
            messages.success(request, "Facture enregistrée avec succès.")
            return redirect("drp:drp_detail", pk=invitation.drp_id)
        return render(request, self.template_name, {
            "form": form,
            "invitation": invitation,
            "drp": invitation.drp,
            "facture_existante": instance,
        })


class AnalyseComparativeView(LoginRequiredMixin, ResponsableAchatRequiredMixin, TemplateView):
    """Page d'analyse IA comparative des prix proforma vs factures par domaine."""

    template_name = "drp/analyse_comparative.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["analyses"] = generer_analyse_ia()
        return ctx


@method_decorator(ratelimit(key="ip", rate="120/h"), name="get")
@method_decorator(ratelimit(key="ip", rate="40/h", method="POST"), name="post")
class SupplierProformaView(DetailView):
    model = Invitation
    template_name = "drp/supplier_proforma.html"
    context_object_name = "invitation"

    def get_object(self, queryset=None):
        token = self.kwargs.get("token")
        if token is None:
            raise Http404
        inv = get_object_or_404(
            Invitation.objects.select_related("drp", "fournisseur"),
            token=token,
        )
        if inv.est_expiree() and inv.statut == Invitation.Statut.ENVOYEE:
            Invitation.objects.filter(pk=inv.pk).update(statut=Invitation.Statut.EXPIREE)
            inv.statut = Invitation.Statut.EXPIREE
        return inv

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inv = self.object
        readonly = (
            inv.drp.statut != DRP.Statut.EN_COURS
            or inv.statut != Invitation.Statut.ENVOYEE
            or inv.est_expiree()
        )
        ctx["readonly"] = readonly
        ctx["form"] = kwargs.get("form") or ProformaResponseForm()
        try:
            ctx["existing_proforma"] = inv.proforma
        except Proforma.DoesNotExist:
            ctx["existing_proforma"] = None
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if (
            self.object.drp.statut != DRP.Statut.EN_COURS
            or self.object.statut != Invitation.Statut.ENVOYEE
            or self.object.est_expiree()
        ):
            messages.error(request, "Ce lien n’est plus valable ou a déjà été utilisé.")
            return self.get(request, *args, **kwargs)
        form = ProformaResponseForm(request.POST, request.FILES)
        if form.is_valid():
            proforma = form.save(commit=False)
            proforma.invitation = self.object
            proforma.save()
            Invitation.objects.filter(pk=self.object.pk).update(statut=Invitation.Statut.REPONDUE)
            messages.success(request, "Votre proforma a été enregistrée. Merci.")
            return redirect("drp:supplier_proforma", token=self.object.token)
        return self.render_to_response(self.get_context_data(form=form))
