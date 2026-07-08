"""Point d'entrée : scénario de démonstration du parc informatique réseau.

Exécute successivement :
1. La construction d'un parc avec 2 sites et des équipements mixtes.
2. Un cycle de vie complet d'incidents (création, prise en charge, résolution).
3. L'affichage d'un rapport d'état et des alertes (bonus).
4. L'export/import JSON de l'état complet du parc.
5. L'export CSV des incidents.
6. La synchronisation SQLite et l'exécution des requêtes métier.
"""

from __future__ import annotations

import logging
import os

os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("data/parc.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from domaine import Firewall, GraviteIncident, ParcInformatiqueError, PointAcces, Routeur, Site, Switch, Parc  # noqa: E402
from persistance import (  # noqa: E402
    GestionnaireBaseDeDonnees,
    afficher_alertes_incidents,
    afficher_rapport_parc,
    exporter_incidents_csv,
    exporter_parc_json,
    importer_parc_json,
)

logger = logging.getLogger(__name__)


def construire_parc_demo() -> Parc:
    """Construit un parc de démonstration avec 2 sites et des équipements mixtes."""
    parc = Parc("ISI Networks")

    dakar = Site("Site Dakar", "Dakar")
    dakar.ajouter_equipement(Routeur("RT-DKR-01", "192.168.1.1", nombre_interfaces=8))
    dakar.ajouter_equipement(Switch("SW-DKR-01", "192.168.1.2", nombre_ports=48))
    dakar.ajouter_equipement(Firewall("FW-DKR-01", "192.168.1.254", politique_defaut="deny"))
    dakar.ajouter_equipement(PointAcces("AP-DKR-01", "192.168.1.10", ssid="ISI-Staff"))
    parc.ajouter_site(dakar)

    thies = Site("Site Thiès", "Thiès")
    thies.ajouter_equipement(Routeur("RT-THS-01", "192.168.2.1"))
    thies.ajouter_equipement(Switch("SW-THS-01", "192.168.2.2"))
    thies.ajouter_equipement(PointAcces("AP-THS-01", "192.168.2.10", ssid="ISI-Guest"))
    parc.ajouter_site(thies)

    return parc


def jouer_scenario_incidents(parc: Parc) -> None:
    """Simule un cycle de vie complet d'incidents sur quelques équipements."""
    dakar = parc.trouver_site("Site Dakar")
    switch_dkr = dakar.trouver_equipement("SW-DKR-01")
    routeur_dkr = dakar.trouver_equipement("RT-DKR-01")

    incident_1 = switch_dkr.declarer_incident("Port 12 ne répond plus", GraviteIncident.MINEURE)
    incident_2 = routeur_dkr.declarer_incident("Perte de connectivité WAN", GraviteIncident.CRITIQUE)

    switch_dkr.prendre_en_charge_incident(incident_1.id)
    switch_dkr.resoudre_incident(incident_1.id)

    routeur_dkr.prendre_en_charge_incident(incident_2.id)
    routeur_dkr.resoudre_incident(incident_2.id)

    try:
        routeur_dkr.resoudre_incident(incident_2.id)  # doit lever IncidentDejaResoluError
    except ParcInformatiqueError as erreur:
        logger.warning("Erreur métier attendue (déjà résolu) : %s", erreur)


def main() -> None:
    """Exécute le scénario de démonstration complet du projet."""
    parc = construire_parc_demo()
    jouer_scenario_incidents(parc)

    afficher_rapport_parc(parc)
    afficher_alertes_incidents(parc, jours=30, seuil=1)

    # --- Persistance JSON ---
    exporter_parc_json(parc, "data/parc_export.json")
    parc_recharge = importer_parc_json("data/parc_export.json")
    print(f"\nParc rechargé depuis JSON : {len(parc_recharge.sites)} site(s).")

    # --- Persistance CSV ---
    nb_lignes = exporter_incidents_csv(parc, "data/incidents_export.csv")
    print(f"Export CSV terminé : {nb_lignes} incident(s).")

    # --- Persistance SQLite + requêtes métier ---
    bd = GestionnaireBaseDeDonnees("data/parc_informatique.db")
    bd.synchroniser_depuis_parc(parc)

    print("\n=== Historique incidents — RT-DKR-01 ===")
    for ligne in bd.historique_incidents_par_equipement("RT-DKR-01"):
        print(ligne)

    print("\n=== Durée moyenne de résolution par équipement ===")
    for ligne in bd.duree_moyenne_resolution_par_equipement():
        print(ligne)

    print("\n=== Top équipements les plus incidentés ===")
    for ligne in bd.equipements_les_plus_incidentes():
        print(ligne)


if __name__ == "__main__":
    main()
