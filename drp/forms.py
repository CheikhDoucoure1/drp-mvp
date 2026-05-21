from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from drp.models import DRP, Domaine, Facture, Fournisseur, Invitation, Proforma


class DomaineForm(forms.ModelForm):
    class Meta:
        model = Domaine
        fields = ("nom",)
        widgets = {
            "nom": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex. Informatique, Logistique…"},
            ),
        }

    def clean_nom(self):
        nom = (self.cleaned_data.get("nom") or "").strip()
        if not nom:
            raise forms.ValidationError("Le nom est obligatoire.")
        qs = Domaine.objects.filter(nom__iexact=nom)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Un domaine avec ce nom existe déjà.")
        return nom


class FournisseurForm(forms.ModelForm):
    domaines = forms.ModelMultipleChoiceField(
        queryset=Domaine.objects.all().order_by("nom"),
        label="Domaines",
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "list-unstyled"}),
    )

    class Meta:
        model = Fournisseur
        fields = ("nom", "email", "telephone", "actif", "domaines")
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "telephone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optionnel"}),
            "actif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nom"].label = "Raison sociale / nom"
        self.fields["telephone"].label = "Téléphone"
        self.fields["actif"].label = "Fournisseur actif (recevoir les invitations)"


class BuyerLoginForm(AuthenticationForm):
    username = forms.CharField(label="Identifiant", widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}))
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )


def _validate_pdf_size(fichier):
    if fichier and fichier.size > settings.MAX_PDF_UPLOAD_BYTES:
        max_mb = settings.MAX_PDF_UPLOAD_BYTES / (1024 * 1024)
        raise forms.ValidationError(f"Le fichier dépasse la taille maximale autorisée ({max_mb:.1f} Mo).")


class DRPForm(forms.ModelForm):
    domaines = forms.ModelMultipleChoiceField(
        queryset=Domaine.objects.all(),
        label="Domaines",
        widget=forms.CheckboxSelectMultiple(attrs={"class": "list-unstyled"}),
        required=True,
    )

    class Meta:
        model = DRP
        fields = (
            "titre",
            "description",
            "fichier",
            "domaines",
            "date_cloture",
            "poids_prix",
            "poids_delai",
        )
        widgets = {
            "titre": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "fichier": forms.FileInput(attrs={"class": "form-control"}),
            "date_cloture": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"},
                format="%Y-%m-%dT%H:%M",
            ),
            "poids_prix": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 100}),
            "poids_delai": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 100}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_cloture"].label = "Date de clôture"
        self.fields["date_cloture"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S%z",
            "%d/%m/%Y %H:%M",
        ]
        if self.instance.pk and self.instance.date_cloture:
            dt = timezone.localtime(self.instance.date_cloture)
            self.initial.setdefault(
                "date_cloture",
                dt.strftime("%Y-%m-%dT%H:%M"),
            )

    def clean_date_cloture(self):
        value = self.cleaned_data["date_cloture"]
        if (
            self.instance.pk
            and self.instance.date_cloture
            and value == self.instance.date_cloture
        ):
            return value
        if value <= timezone.now():
            raise forms.ValidationError("La date de clôture doit être strictement dans le futur.")
        return value

    def clean_fichier(self):
        fichier = self.cleaned_data.get("fichier")
        if fichier:
            _validate_pdf_size(fichier)
            return fichier
        if self.instance.pk and self.instance.fichier:
            return self.instance.fichier
        return fichier


class ProformaResponseForm(forms.ModelForm):
    class Meta:
        model = Proforma
        fields = ("prix", "delai_jours", "commentaire", "fichier")
        labels = {
            "prix": "Prix (FCFA)",
            "delai_jours": "Délai (jours)",
            "commentaire": "Commentaire",
            "fichier": "Proforma (PDF)",
        }
        widgets = {
            "prix": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "delai_jours": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "commentaire": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "fichier": forms.FileInput(attrs={"class": "form-control"}),
        }

    def clean_fichier(self):
        fichier = self.cleaned_data.get("fichier")
        _validate_pdf_size(fichier)
        return fichier


class DRPChangeStatutForm(forms.Form):
    """Changement de statut métier (hors attribution fournisseur)."""

    statut = forms.ChoiceField(
        label="Nouveau statut",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, drp=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.drp = drp
        if drp is not None:
            self.fields["statut"].choices = [
                (value, label) for value, label in DRP.Statut.choices if value != drp.statut
            ]

    def clean_statut(self):
        value = self.cleaned_data["statut"]
        if self.drp is not None and value == self.drp.statut:
            raise forms.ValidationError("Choisissez un statut différent de l’actuel.")
        return value


class FactureForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = ("numero", "montant", "date_facture")
        widgets = {
            "numero": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. FAC-2024-001"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "date_facture": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }


class SelectWinnerForm(forms.Form):
    invitation = forms.ModelChoiceField(
        queryset=Invitation.objects.none(),
        label="Fournisseur retenu",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, drp=None, **kwargs):
        super().__init__(*args, **kwargs)
        if drp is not None:
            ids = (
                Proforma.objects.filter(invitation__drp=drp)
                .values_list("invitation_id", flat=True)
            )
            self.fields["invitation"].queryset = Invitation.objects.filter(
                pk__in=ids,
                drp=drp,
            ).select_related("fournisseur")
