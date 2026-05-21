from django.contrib import admin

from drp.models import Domaine, DRP, Fournisseur, Invitation, Proforma


@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    search_fields = ("nom",)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "email", "telephone", "actif")
    list_filter = ("actif",)
    search_fields = ("nom", "email")
    filter_horizontal = ("domaines",)


class InvitationInline(admin.TabularInline):
    model = Invitation
    extra = 0
    readonly_fields = ("token", "expiration", "statut", "fournisseur")
    can_delete = False


@admin.register(DRP)
class DRPAdmin(admin.ModelAdmin):
    list_display = ("titre", "statut", "date_cloture", "created_at", "created_by")
    list_filter = ("statut",)
    search_fields = ("titre",)
    readonly_fields = ("created_at", "selected_invitation")
    inlines = [InvitationInline]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("drp", "fournisseur", "statut", "expiration", "token")
    list_filter = ("statut",)
    readonly_fields = ("token",)


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = ("invitation", "prix", "delai_jours", "submitted_at")
    readonly_fields = ("submitted_at",)
