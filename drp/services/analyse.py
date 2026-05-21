"""
Service d'analyse comparative des prix par domaine.

Pour chaque domaine, agrège les proformas fournisseurs et les factures réelles,
puis appelle Claude pour produire une analyse en français.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Avg, Count, Q

from drp.models import Domaine, DRP, Facture, Proforma


@dataclass
class LigneComparaison:
    drp_titre: str
    fournisseur_nom: str
    prix_proforma: Decimal
    montant_facture: Decimal | None
    ecart: Decimal | None          # facture − proforma
    ecart_pct: float | None        # en %


@dataclass
class AnalyseDomaine:
    domaine: Domaine
    lignes: list[LigneComparaison] = field(default_factory=list)
    nb_proformas: int = 0
    nb_factures: int = 0
    moy_proforma: Decimal | None = None
    moy_facture: Decimal | None = None
    moy_ecart_pct: float | None = None
    commentaire_ia: str = ""


def _build_analyses(domaines=None) -> list[AnalyseDomaine]:
    """Construit les données statistiques par domaine."""
    if domaines is None:
        domaines = Domaine.objects.all().order_by("nom")

    analyses = []
    for domaine in domaines:
        proformas = (
            Proforma.objects.filter(invitation__drp__domaines=domaine)
            .select_related(
                "invitation__fournisseur",
                "invitation__drp",
                "invitation__facture",
            )
            .order_by("invitation__drp__titre", "prix")
        )

        lignes: list[LigneComparaison] = []
        somme_proforma = Decimal("0")
        somme_facture = Decimal("0")
        nb_factures = 0

        for p in proformas:
            try:
                facture = p.invitation.facture
                montant_facture = facture.montant
                ecart = montant_facture - p.prix
                ecart_pct = float(ecart / p.prix * 100) if p.prix else None
                somme_facture += montant_facture
                nb_factures += 1
            except Facture.DoesNotExist:
                montant_facture = None
                ecart = None
                ecart_pct = None

            somme_proforma += p.prix
            lignes.append(
                LigneComparaison(
                    drp_titre=p.invitation.drp.titre,
                    fournisseur_nom=p.invitation.fournisseur.nom,
                    prix_proforma=p.prix,
                    montant_facture=montant_facture,
                    ecart=ecart,
                    ecart_pct=ecart_pct,
                )
            )

        nb_proformas = len(lignes)
        moy_proforma = (somme_proforma / nb_proformas) if nb_proformas else None
        moy_facture = (somme_facture / nb_factures) if nb_factures else None
        ecarts = [l.ecart_pct for l in lignes if l.ecart_pct is not None]
        moy_ecart_pct = (sum(ecarts) / len(ecarts)) if ecarts else None

        analyses.append(
            AnalyseDomaine(
                domaine=domaine,
                lignes=lignes,
                nb_proformas=nb_proformas,
                nb_factures=nb_factures,
                moy_proforma=moy_proforma,
                moy_facture=moy_facture,
                moy_ecart_pct=moy_ecart_pct,
            )
        )

    return [a for a in analyses if a.nb_proformas > 0]


def _prompt_pour_domaine(analyse: AnalyseDomaine) -> str:
    lignes_txt = "\n".join(
        f"  - DRP « {l.drp_titre} » | Fournisseur : {l.fournisseur_nom} "
        f"| Proforma : {l.prix_proforma:,.0f} FCFA"
        + (f" | Facture : {l.montant_facture:,.0f} FCFA (écart : {l.ecart_pct:+.1f}%)" if l.montant_facture else " | Facture : non disponible")
        for l in analyse.lignes
    )
    stats = (
        f"Nombre de proformas : {analyse.nb_proformas}\n"
        f"Nombre de factures enregistrées : {analyse.nb_factures}\n"
    )
    if analyse.moy_proforma:
        stats += f"Prix moyen proforma : {analyse.moy_proforma:,.0f} FCFA\n"
    if analyse.moy_facture:
        stats += f"Montant moyen facturé : {analyse.moy_facture:,.0f} FCFA\n"
    if analyse.moy_ecart_pct is not None:
        stats += f"Écart moyen proforma→facture : {analyse.moy_ecart_pct:+.1f}%\n"

    return (
        f"Tu es un analyste achats senior. Voici les données de comparaison des prix "
        f"pour le domaine « {analyse.domaine.nom} » :\n\n"
        f"{stats}\n"
        f"Détail ligne par ligne :\n{lignes_txt}\n\n"
        "En 3 à 5 phrases concises en français, fournis une analyse critique de ces données : "
        "tendances des écarts proforma/facture, fournisseurs à surveiller, risques de surcoût, "
        "et recommandations concrètes pour les prochains achats dans ce domaine. "
        "Ne répète pas les chiffres bruts, concentre-toi sur l'interprétation et les actions."
    )


def generer_analyse_ia(domaines=None) -> list[AnalyseDomaine]:
    """
    Construit les analyses statistiques et, si la clé ANTHROPIC_API_KEY est disponible,
    enrichit chaque domaine avec un commentaire généré par Claude.
    """
    analyses = _build_analyses(domaines)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        for a in analyses:
            a.commentaire_ia = (
                "Clé ANTHROPIC_API_KEY non configurée — "
                "renseignez-la dans votre fichier .env pour activer l'analyse IA."
            )
        return analyses

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        for analyse in analyses:
            if analyse.nb_proformas == 0:
                continue
            prompt = _prompt_pour_domaine(analyse)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            analyse.commentaire_ia = response.content[0].text.strip()
    except Exception as exc:
        for a in analyses:
            if not a.commentaire_ia:
                a.commentaire_ia = f"Erreur lors de l'analyse IA : {exc}"

    return analyses
