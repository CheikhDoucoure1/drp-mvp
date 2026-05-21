from django.urls import path

from drp import views

app_name = "drp"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("login/", views.BuyerLoginView.as_view(), name="login"),
    path("logout/", views.BuyerLogoutView.as_view(), name="logout"),
    path("domaines/", views.DomaineListView.as_view(), name="domaine_list"),
    path("domaines/nouveau/", views.DomaineCreateView.as_view(), name="domaine_create"),
    path("domaines/<int:pk>/modifier/", views.DomaineUpdateView.as_view(), name="domaine_update"),
    path("domaines/<int:pk>/supprimer/", views.DomaineDeleteView.as_view(), name="domaine_delete"),
    path("fournisseurs/", views.FournisseurListView.as_view(), name="fournisseur_list"),
    path("fournisseurs/nouveau/", views.FournisseurCreateView.as_view(), name="fournisseur_create"),
    path("fournisseurs/<int:pk>/modifier/", views.FournisseurUpdateView.as_view(), name="fournisseur_update"),
    path("fournisseurs/<int:pk>/desactiver/", views.FournisseurDesactiverView.as_view(), name="fournisseur_desactiver"),
    path("drp/nouvelle/", views.DRPCreateView.as_view(), name="drp_create"),
    path("drp/<int:pk>/modifier/", views.DRPUpdateView.as_view(), name="drp_update"),
    path("drp/<int:pk>/", views.DRPDetailView.as_view(), name="drp_detail"),
    path("drp/<int:pk>/supprimer/", views.DRPDeleteView.as_view(), name="drp_delete"),
    path("drp/<int:drp_pk>/facture/", views.FactureCreateView.as_view(), name="facture_create"),
    path("analyse/", views.AnalyseComparativeView.as_view(), name="analyse_comparative"),
    path("f/<uuid:token>/", views.SupplierProformaView.as_view(), name="supplier_proforma"),
]
