"""Vérifications d’accès aux routes (statuts HTTP attendus)."""

import uuid
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from drp.constants import RESPONSABLE_ACHAT_GROUP_NAME
from drp.models import Domaine, DRP, Fournisseur, Invitation


class DrpRouteAccessTests(TestCase):
    """Toutes les routes nommées `drp:` doivent répondre sans 404 ni 500 pour les bons rôles."""

    @classmethod
    def setUpTestData(cls):
        cls.group, _ = Group.objects.get_or_create(name=RESPONSABLE_ACHAT_GROUP_NAME)
        cls.buyer = User.objects.create_user("buyer_routes", password="pw-test-routes-1")
        cls.buyer.groups.add(cls.group)
        cls.other = User.objects.create_user("other_routes", password="pw-test-routes-2")
        cls.domaine = Domaine.objects.create(nom="Domaine route test")
        cls.fournisseur = Fournisseur.objects.create(
            nom="F route",
            email="f.route@example.com",
        )
        cls.fournisseur.domaines.add(cls.domaine)
        cls.drp = DRP.objects.create(
            titre="DRP route test",
            description="Desc",
            date_cloture=timezone.now() + timedelta(days=7),
            created_by=cls.buyer,
            statut=DRP.Statut.EN_COURS,
        )
        cls.drp.domaines.add(cls.domaine)
        cls.inv = Invitation.objects.create(
            fournisseur=cls.fournisseur,
            drp=cls.drp,
            expiration=cls.drp.date_cloture,
            statut=Invitation.Statut.ENVOYEE,
        )

    def _names(self):
        return [
            "dashboard",
            "login",
            "logout",
            "domaine_list",
            "domaine_create",
            "fournisseur_list",
            "fournisseur_create",
            "drp_create",
            "drp_detail",
            "drp_update",
            "drp_delete",
            "domaine_update",
            "domaine_delete",
            "fournisseur_update",
            "fournisseur_desactiver",
            "supplier_proforma",
        ]

    def test_reverse_all_named_routes(self):
        for name in self._names():
            with self.subTest(name=name):
                if name == "supplier_proforma":
                    reverse("drp:supplier_proforma", kwargs={"token": self.inv.token})
                elif name in (
                    "domaine_update",
                    "domaine_delete",
                    "fournisseur_update",
                    "fournisseur_desactiver",
                    "drp_detail",
                    "drp_update",
                    "drp_delete",
                ):
                    pk = {
                        "domaine_update": self.domaine.pk,
                        "domaine_delete": self.domaine.pk,
                        "fournisseur_update": self.fournisseur.pk,
                        "fournisseur_desactiver": self.fournisseur.pk,
                        "drp_detail": self.drp.pk,
                        "drp_update": self.drp.pk,
                        "drp_delete": self.drp.pk,
                    }[name]
                    reverse(f"drp:{name}", kwargs={"pk": pk})
                else:
                    reverse(f"drp:{name}")

    def test_anonymous_login_and_supplier_only(self):
        c = Client()
        self.assertEqual(c.get(reverse("drp:login")).status_code, 200)
        self.assertEqual(c.get(reverse("drp:logout")).status_code, 302)

        for name in self._names():
            if name in ("login", "supplier_proforma"):
                continue
            with self.subTest(name=name):
                url = self._url(name)
                r = c.get(url, follow=False)
                self.assertIn(
                    r.status_code,
                    (302, 301),
                    msg=f"{name} doit rediriger les anonymes vers la connexion",
                )
                if r.status_code in (301, 302):
                    self.assertIn("/login/", r["Location"])

        r_sup = c.get(reverse("drp:supplier_proforma", kwargs={"token": self.inv.token}))
        self.assertEqual(r_sup.status_code, 200)

        bad = uuid.uuid4()
        self.assertEqual(c.get(reverse("drp:supplier_proforma", kwargs={"token": bad})).status_code, 404)

    def test_buyer_reaches_buyer_pages(self):
        c = Client()
        self.assertTrue(c.login(username="buyer_routes", password="pw-test-routes-1"))
        for name in self._names():
            if name == "supplier_proforma":
                continue
            with self.subTest(name=name):
                url = self._url(name)
                r = c.get(url)
                self.assertIn(r.status_code, (200, 302), msg=f"{name} -> {r.status_code}")

    def test_other_user_403_on_dashboard(self):
        c = Client()
        self.assertTrue(c.login(username="other_routes", password="pw-test-routes-2"))
        r = c.get(reverse("drp:dashboard"))
        self.assertEqual(r.status_code, 403)

    def test_logout_get_shows_confirm_when_authenticated(self):
        c = Client()
        self.assertTrue(c.login(username="buyer_routes", password="pw-test-routes-1"))
        r = c.get(reverse("drp:logout"))
        self.assertEqual(r.status_code, 200)
        r2 = c.post(reverse("drp:logout"))
        self.assertEqual(r2.status_code, 302)
        self.assertIn("/login/", r2["Location"])

    def _url(self, name: str) -> str:
        if name == "supplier_proforma":
            return reverse("drp:supplier_proforma", kwargs={"token": self.inv.token})
        if name in (
            "domaine_update",
            "domaine_delete",
            "fournisseur_update",
            "fournisseur_desactiver",
            "drp_detail",
            "drp_update",
            "drp_delete",
        ):
            pk = {
                "domaine_update": self.domaine.pk,
                "domaine_delete": self.domaine.pk,
                "fournisseur_update": self.fournisseur.pk,
                "fournisseur_desactiver": self.fournisseur.pk,
                "drp_detail": self.drp.pk,
                "drp_update": self.drp.pk,
                "drp_delete": self.drp.pk,
            }[name]
            return reverse(f"drp:{name}", kwargs={"pk": pk})
        return reverse(f"drp:{name}")
