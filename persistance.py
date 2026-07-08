"""Couche de persistance et de rapports du parc informatique réseau.

Regroupe dans un seul fichier :
- l'export/import JSON de l'état complet du parc (sites + équipements + incidents)
- l'export CSV des incidents (avec filtrage par période)
- la persistance SQLite (2 tables liées + requêtes métier)
- les fonctions d'affichage de rapports (couche présentation)
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from domaine import (
    EquipementBase,
    EtatEquipement,
    FABRIQUE_EQUIPEMENTS,
    Firewall,
    Incident,
    Parc,
    PointAcces,
    Routeur,
    Site,
    Switch,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Persistance JSON — état complet du parc
# ---------------------------------------------------------------------------

def exporter_parc_json(parc: Parc, chemin: str) -> None:
    """Exporte l'état complet du parc (sites + équipements + incidents) en JSON."""
    data = {
        "nom_entreprise": parc.nom_entreprise,
        "sites": [
            {
                "nom": site.nom,
                "ville": site.ville,
                "equipements": [eq.to_dict() for eq in site.equipements],
            }
            for site in parc.sites
        ],
    }
    with open(chemin, "w", encoding="utf-8") as fichier:
        json.dump(data, fichier, ensure_ascii=False, indent=2)
    logger.info("Parc exporté vers %s", chemin)


def _reconstruire_equipement(data: dict) -> EquipementBase:
    """Recrée l'objet équipement concret adapté à partir du dictionnaire JSON."""
    type_eq = data["type_equipement"]
    classe = FABRIQUE_EQUIPEMENTS.get(type_eq)
    if classe is None:
        raise ValueError(f"Type d'équipement inconnu dans le fichier JSON : '{type_eq}'.")

    if classe is Routeur:
        equipement: EquipementBase = Routeur(data["nom"], data["adresse_ip"], data.get("nombre_interfaces", 4))
        equipement.protocole_routage = data.get("protocole_routage", "statique")
    elif classe is Switch:
        equipement = Switch(data["nom"], data["adresse_ip"], data.get("nombre_ports", 24))
        equipement.vlans = data.get("vlans", [])
    elif classe is Firewall:
        equipement = Firewall(data["nom"], data["adresse_ip"], data.get("politique_defaut", "deny"))
        equipement.regles = data.get("regles", [])
    else:  # PointAcces
        equipement = PointAcces(data["nom"], data["adresse_ip"], data.get("ssid", "reseau"))
        equipement.bande_frequence = data.get("bande_frequence", "2.4GHz")

    equipement.etat = EtatEquipement(data["etat"])
    for incident_data in data.get("incidents", []):
        equipement._incidents.append(Incident.from_dict(incident_data))  # pylint: disable=protected-access
    return equipement


def importer_parc_json(chemin: str) -> Parc:
    """Recharge un parc complet depuis un fichier JSON précédemment exporté."""
    fichier_path = Path(chemin)
    if not fichier_path.exists():
        raise FileNotFoundError(f"Fichier JSON introuvable : '{chemin}'.")

    with open(fichier_path, "r", encoding="utf-8") as fichier:
        data = json.load(fichier)

    parc = Parc(data["nom_entreprise"])
    for site_data in data["sites"]:
        site = Site(site_data["nom"], site_data["ville"])
        for eq_data in site_data["equipements"]:
            site.ajouter_equipement(_reconstruire_equipement(eq_data))
        parc.ajouter_site(site)
    logger.info("Parc importé depuis %s (%d site(s))", chemin, len(parc.sites))
    return parc


# ---------------------------------------------------------------------------
# Persistance CSV — export des incidents avec filtrage par période
# ---------------------------------------------------------------------------

_ENTETES_CSV = [
    "site", "equipement", "incident_id", "description",
    "gravite", "statut", "date_ouverture", "date_resolution", "duree_resolution_heures",
]


def exporter_incidents_csv(
    parc: Parc,
    chemin: str,
    date_debut: Optional[datetime] = None,
    date_fin: Optional[datetime] = None,
) -> int:
    """Exporte les incidents du parc en CSV, filtrés sur une période optionnelle.

    Retourne le nombre de lignes écrites.
    """
    lignes_ecrites = 0
    with open(chemin, "w", newline="", encoding="utf-8") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=_ENTETES_CSV)
        writer.writeheader()
        for site, equipement in parc.tous_les_equipements():
            for incident in equipement.incidents:
                if date_debut and incident.date_ouverture < date_debut:
                    continue
                if date_fin and incident.date_ouverture > date_fin:
                    continue
                writer.writerow({
                    "site": site.nom,
                    "equipement": equipement.nom,
                    "incident_id": incident.id,
                    "description": incident.description,
                    "gravite": incident.gravite.value,
                    "statut": incident.statut.value,
                    "date_ouverture": incident.date_ouverture.isoformat(),
                    "date_resolution": incident.date_resolution.isoformat() if incident.date_resolution else "",
                    "duree_resolution_heures": incident.duree_resolution_heures() or "",
                })
                lignes_ecrites += 1
    logger.info("Export CSV terminé : %d incident(s) écrit(s) dans %s", lignes_ecrites, chemin)
    return lignes_ecrites


# ---------------------------------------------------------------------------
# Persistance SQLite — tables liées + requêtes métier
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS equipements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    site TEXT NOT NULL,
    type_equipement TEXT NOT NULL,
    adresse_ip TEXT NOT NULL,
    etat TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipement_id INTEGER NOT NULL,
    incident_ref TEXT NOT NULL,
    description TEXT NOT NULL,
    gravite TEXT NOT NULL,
    statut TEXT NOT NULL,
    date_ouverture TEXT NOT NULL,
    date_resolution TEXT,
    FOREIGN KEY (equipement_id) REFERENCES equipements(id)
);
"""


class GestionnaireBaseDeDonnees:
    """Encapsule l'accès à la base SQLite (tables `equipements` / `interventions`)."""

    def __init__(self, chemin_bd: str = "data/parc_informatique.db") -> None:
        self.chemin_bd = chemin_bd
        self._initialiser_schema()

    @contextmanager
    def _connexion(self) -> Iterator[sqlite3.Connection]:
        """Fournit une connexion SQLite avec gestion automatique de commit/fermeture."""
        connexion = sqlite3.connect(self.chemin_bd)
        connexion.execute("PRAGMA foreign_keys = ON;")
        try:
            yield connexion
            connexion.commit()
        except sqlite3.Error:
            connexion.rollback()
            raise
        finally:
            connexion.close()

    def _initialiser_schema(self) -> None:
        with self._connexion() as connexion:
            connexion.executescript(_SCHEMA_SQL)
        logger.info("Schéma SQLite initialisé (%s)", self.chemin_bd)

    def synchroniser_depuis_parc(self, parc: Parc) -> None:
        """Vide puis réinsère les données SQLite à partir de l'état actuel du parc."""
        with self._connexion() as connexion:
            connexion.execute("DELETE FROM interventions;")
            connexion.execute("DELETE FROM equipements;")
            for site, equipement in parc.tous_les_equipements():
                curseur = connexion.execute(
                    "INSERT INTO equipements (nom, site, type_equipement, adresse_ip, etat) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (equipement.nom, site.nom, equipement.type_equipement.value,
                     equipement.adresse_ip, equipement.etat.value),
                )
                equipement_id = curseur.lastrowid
                for incident in equipement.incidents:
                    connexion.execute(
                        "INSERT INTO interventions "
                        "(equipement_id, incident_ref, description, gravite, statut, "
                        " date_ouverture, date_resolution) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (equipement_id, incident.id, incident.description, incident.gravite.value,
                         incident.statut.value, incident.date_ouverture.isoformat(),
                         incident.date_resolution.isoformat() if incident.date_resolution else None),
                    )
        logger.info("Synchronisation SQLite terminée.")

    # --- Requêtes métier (5 au total, aucune n'est un simple SELECT *) ---

    def historique_incidents_par_equipement(self, nom_equipement: str) -> List[Tuple]:
        """Historique complet des interventions pour un équipement donné."""
        with self._connexion() as connexion:
            return connexion.execute(
                "SELECT i.incident_ref, i.description, i.gravite, i.statut, "
                "       i.date_ouverture, i.date_resolution "
                "FROM interventions i JOIN equipements e ON e.id = i.equipement_id "
                "WHERE e.nom = ? ORDER BY i.date_ouverture DESC",
                (nom_equipement,),
            ).fetchall()

    def equipements_en_panne_par_site(self, nom_site: str) -> List[Tuple]:
        """Liste des équipements en panne pour un site donné."""
        with self._connexion() as connexion:
            return connexion.execute(
                "SELECT nom, type_equipement, adresse_ip FROM equipements "
                "WHERE site = ? AND etat = 'en_panne'",
                (nom_site,),
            ).fetchall()

    def duree_moyenne_resolution_par_equipement(self) -> List[Tuple]:
        """Durée moyenne de résolution (heures) des incidents résolus, par équipement."""
        with self._connexion() as connexion:
            return connexion.execute(
                "SELECT e.nom, "
                "       ROUND(AVG((julianday(i.date_resolution) - julianday(i.date_ouverture)) * 24), 2) "
                "       AS duree_moyenne_heures, COUNT(*) AS nb_incidents_resolus "
                "FROM interventions i JOIN equipements e ON e.id = i.equipement_id "
                "WHERE i.statut = 'resolu' GROUP BY e.nom ORDER BY duree_moyenne_heures DESC",
            ).fetchall()

    def nombre_incidents_par_site_et_gravite(self) -> List[Tuple]:
        """Répartition du nombre d'incidents par site et par niveau de gravité."""
        with self._connexion() as connexion:
            return connexion.execute(
                "SELECT e.site, i.gravite, COUNT(*) AS nb_incidents "
                "FROM interventions i JOIN equipements e ON e.id = i.equipement_id "
                "GROUP BY e.site, i.gravite ORDER BY e.site, nb_incidents DESC",
            ).fetchall()

    def equipements_les_plus_incidentes(self, limite: int = 5) -> List[Tuple]:
        """Top N des équipements ayant connu le plus d'incidents (toutes gravités)."""
        with self._connexion() as connexion:
            return connexion.execute(
                "SELECT e.nom, e.site, COUNT(i.id) AS nb_incidents "
                "FROM equipements e LEFT JOIN interventions i ON i.equipement_id = e.id "
                "GROUP BY e.nom, e.site ORDER BY nb_incidents DESC LIMIT ?",
                (limite,),
            ).fetchall()


# ---------------------------------------------------------------------------
# Rapports (couche affichage, séparée de la logique métier et de l'accès aux données)
# ---------------------------------------------------------------------------

def afficher_rapport_parc(parc: Parc) -> None:
    """Affiche un rapport lisible de l'état du parc, site par site."""
    print(f"\n=== Rapport du parc informatique — {parc.nom_entreprise} ===")
    for rapport in parc.rapport_global():
        print(
            f"- Site {rapport['site']} ({rapport['ville']}) : "
            f"{rapport['total_equipements']} équipement(s) | "
            f"{rapport['actifs']} actif(s) | "
            f"{rapport['en_panne']} en panne | "
            f"{rapport['en_maintenance']} en maintenance"
        )


def afficher_alertes_incidents(parc: Parc, jours: int = 7, seuil: int = 3) -> None:
    """Affiche les équipements ayant dépassé un seuil d'incidents sur une période (bonus)."""
    alertes = parc.equipements_en_alerte(jours=jours, seuil=seuil)
    if not alertes:
        print(f"\nAucune alerte : aucun équipement n'a dépassé {seuil} incident(s) sur {jours} jour(s).")
        return
    print(f"\n=== Alertes ({seuil}+ incidents sur {jours} jour(s)) ===")
    for site_nom, equipement_nom, nb in alertes:
        logger.warning("Alerte incidents : %s (site %s) — %d incident(s)", equipement_nom, site_nom, nb)
        print(f"- ALERTE : {equipement_nom} (site {site_nom}) — {nb} incident(s) récents")
