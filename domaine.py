"""Couche domaine (métier) du parc informatique réseau.

Regroupe volontairement dans un seul fichier, pour faciliter la lecture et
la soutenance orale :
- les Enum du domaine
- les exceptions personnalisées
- la classe Incident (composition : créé et possédé par un Equipement)
- la classe abstraite EquipementBase et ses 4 classes filles concrètes
- la classe Site (agrégation : reçoit des équipements créés en dehors d'elle)
- la classe Parc (regroupe l'ensemble des sites de l'entreprise)
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------
# Les énumérations définissent les valeurs métier autorisées pour les
# équipements, leurs états et les incidents. Elles servent à éviter les
# erreurs de saisie et à rendre le code plus lisible et robuste.

class TypeEquipement(Enum):
    """Types d'équipements réseau gérés par le parc."""

    ROUTEUR = "routeur"
    SWITCH = "switch"
    FIREWALL = "firewall"
    POINT_ACCES = "point_acces"


class EtatEquipement(Enum):
    """États possibles d'un équipement réseau."""

    ACTIF = "actif"
    INACTIF = "inactif"
    EN_PANNE = "en_panne"
    MAINTENANCE = "maintenance"


class GraviteIncident(Enum):
    """Niveau de gravité d'un incident technique."""

    MINEURE = "mineure"
    MAJEURE = "majeure"
    CRITIQUE = "critique"


class StatutIncident(Enum):
    """Statut du cycle de vie d'un incident."""

    OUVERT = "ouvert"
    EN_COURS = "en_cours"
    RESOLU = "resolu"


# ---------------------------------------------------------------------------
# Exceptions personnalisées
# ---------------------------------------------------------------------------

class ParcInformatiqueError(Exception):
    """Exception de base pour toutes les erreurs métier du parc informatique."""


class EquipementIntrouvableError(ParcInformatiqueError):
    """Levée quand un équipement demandé n'existe pas dans le site/parc."""

    def __init__(self, identifiant: str) -> None:
        self.identifiant = identifiant
        super().__init__(
            f"Aucun équipement trouvé avec l'identifiant/nom : '{identifiant}'."
        )


class AdresseIPInvalideError(ParcInformatiqueError):
    """Levée quand une adresse IP fournie ne respecte pas le format attendu."""

    def __init__(self, adresse_ip: str) -> None:
        self.adresse_ip = adresse_ip
        super().__init__(f"Adresse IP invalide : '{adresse_ip}'.")


class IncidentDejaResoluError(ParcInformatiqueError):
    """Levée quand on tente de modifier un incident déjà marqué comme résolu."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = incident_id
        super().__init__(
            f"L'incident '{incident_id}' est déjà résolu et ne peut plus être modifié."
        )


class EquipementIndisponibleError(ParcInformatiqueError):
    """Levée quand une opération est impossible car l'équipement est hors service."""

    def __init__(self, nom: str, etat: str) -> None:
        self.nom = nom
        self.etat = etat
        super().__init__(
            f"L'équipement '{nom}' est dans l'état '{etat}' et ne peut pas effectuer cette opération."
        )


# ---------------------------------------------------------------------------
# Incident (composition avec Equipement)
# ---------------------------------------------------------------------------
# Un incident ne peut exister que dans le contexte d'un équipement.
# Cette relation de composition est importante, car elle signifie que
# la vie d'un incident dépend entièrement de l'équipement qui l'a généré.

class Incident:
    """Représente un incident technique survenu sur un équipement.

    Un Incident n'a pas de sens en dehors de son équipement : il est créé et
    n'existe qu'à travers lui (relation de composition), contrairement à un
    Equipement qui peut exister indépendamment d'un Site (agrégation).
    """

    _compteur: int = 0

    def __init__(
        self,
        description: str,
        gravite: GraviteIncident,
        date_ouverture: Optional[datetime] = None,
    ) -> None:
        if not description or not description.strip():
            raise ValueError("La description d'un incident ne peut pas être vide.")

        Incident._compteur += 1
        self.id: str = f"INC-{Incident._compteur:05d}"
        self.description: str = description.strip()
        self.gravite: GraviteIncident = gravite
        self.statut: StatutIncident = StatutIncident.OUVERT
        self.date_ouverture: datetime = date_ouverture or datetime.now()
        self.date_resolution: Optional[datetime] = None
        logger.info("Incident créé : %s (%s)", self.id, self.gravite.value)

    def prendre_en_charge(self) -> None:
        """Passe l'incident au statut EN_COURS."""
        if self.statut == StatutIncident.RESOLU:
            raise IncidentDejaResoluError(self.id)
        self.statut = StatutIncident.EN_COURS
        logger.info("Incident %s pris en charge.", self.id)

    def resoudre(self, date_resolution: Optional[datetime] = None) -> None:
        """Marque l'incident comme résolu et fige sa date de résolution."""
        if self.statut == StatutIncident.RESOLU:
            raise IncidentDejaResoluError(self.id)
        self.statut = StatutIncident.RESOLU
        self.date_resolution = date_resolution or datetime.now()
        logger.info("Incident %s résolu.", self.id)

    def duree_resolution_heures(self) -> Optional[float]:
        """Retourne la durée de résolution en heures, ou None si non résolu."""
        if self.date_resolution is None:
            return None
        delta = self.date_resolution - self.date_ouverture
        return round(delta.total_seconds() / 3600, 2)

    def to_dict(self) -> dict:
        """Sérialise l'incident en dictionnaire (pour export JSON)."""
        return {
            "id": self.id,
            "description": self.description,
            "gravite": self.gravite.value,
            "statut": self.statut.value,
            "date_ouverture": self.date_ouverture.isoformat(),
            "date_resolution": (
                self.date_resolution.isoformat() if self.date_resolution else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Incident":
        """Reconstruit un Incident depuis un dictionnaire JSON."""
        incident = cls(
            description=data["description"],
            gravite=GraviteIncident(data["gravite"]),
            date_ouverture=datetime.fromisoformat(data["date_ouverture"]),
        )
        incident.id = data["id"]
        incident.statut = StatutIncident(data["statut"])
        if data.get("date_resolution"):
            incident.date_resolution = datetime.fromisoformat(data["date_resolution"])
        return incident

    def __repr__(self) -> str:
        return f"Incident({self.id}, {self.statut.value}, {self.gravite.value})"


# ---------------------------------------------------------------------------
# Hiérarchie des équipements (classe abstraite + 4 classes filles)
# ---------------------------------------------------------------------------
# La classe abstraite EquipementBase impose un contrat commun à tous les
# équipements réseau. Les classes concrètes héritent de ce contrat tout en
# ajoutant des comportements spécifiques à leur type (routeur, switch, etc.).

_IPV4_REGEX = re.compile(
    r"^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
    r"(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}$"
)


class EquipementBase(ABC):
    """Classe abstraite représentant un équipement réseau générique.

    Impose un contrat via les méthodes abstraites `ping()` et `configurer()`.
    Chaque équipement possède (composition) sa propre liste d'incidents.
    """

    def __init__(self, nom: str, adresse_ip: str, type_equipement: TypeEquipement) -> None:
        if not nom or not nom.strip():
            raise ValueError("Le nom de l'équipement ne peut pas être vide.")
        if not _IPV4_REGEX.match(adresse_ip):
            raise AdresseIPInvalideError(adresse_ip)

        self.nom: str = nom.strip()
        self.adresse_ip: str = adresse_ip
        self.type_equipement: TypeEquipement = type_equipement
        self.etat: EtatEquipement = EtatEquipement.ACTIF
        self.date_installation: datetime = datetime.now()
        self._incidents: List[Incident] = []  # composition
        logger.info(
            "Équipement créé : %s (%s, %s)", self.nom, self.type_equipement.value, self.adresse_ip
        )

    @abstractmethod
    def ping(self) -> bool:
        """Simule un test de connectivité vers l'équipement."""
        raise NotImplementedError

    @abstractmethod
    def configurer(self, **parametres) -> None:
        """Applique une configuration spécifique à ce type d'équipement."""
        raise NotImplementedError

    def changer_etat(self, nouvel_etat: EtatEquipement) -> None:
        """Change l'état de l'équipement (ex : passage en maintenance)."""
        logger.info("Équipement %s : %s -> %s", self.nom, self.etat.value, nouvel_etat.value)
        self.etat = nouvel_etat

    def declarer_incident(self, description: str, gravite: GraviteIncident) -> Incident:
        """Crée un nouvel incident rattaché à cet équipement (composition)."""
        incident = Incident(description=description, gravite=gravite)
        self._incidents.append(incident)
        if gravite == GraviteIncident.CRITIQUE:
            self.changer_etat(EtatEquipement.EN_PANNE)
        return incident

    def resoudre_incident(self, incident_id: str) -> Incident:
        """Marque un incident comme résolu et remet l'équipement en service si possible."""
        incident = self._trouver_incident(incident_id)
        incident.resoudre()
        if self.etat == EtatEquipement.EN_PANNE:
            self.changer_etat(EtatEquipement.ACTIF)
        return incident

    def prendre_en_charge_incident(self, incident_id: str) -> Incident:
        """Passe un incident au statut EN_COURS."""
        incident = self._trouver_incident(incident_id)
        incident.prendre_en_charge()
        return incident

    def _trouver_incident(self, incident_id: str) -> Incident:
        for incident in self._incidents:
            if incident.id == incident_id:
                return incident
        raise ValueError(f"Aucun incident '{incident_id}' trouvé sur l'équipement '{self.nom}'.")

    @property
    def incidents(self) -> List[Incident]:
        """Retourne une copie de la liste des incidents (protège l'encapsulation)."""
        return list(self._incidents)

    def nombre_incidents_sur_periode(self, jours: int) -> int:
        """Compte les incidents ouverts au cours des N derniers jours (pour alerte)."""
        seuil = datetime.now().timestamp() - jours * 86400
        return sum(1 for inc in self._incidents if inc.date_ouverture.timestamp() >= seuil)

    def to_dict(self) -> dict:
        """Sérialise l'équipement (attributs communs + spécifiques + incidents)."""
        return {
            "nom": self.nom,
            "adresse_ip": self.adresse_ip,
            "type_equipement": self.type_equipement.value,
            "etat": self.etat.value,
            "date_installation": self.date_installation.isoformat(),
            "incidents": [inc.to_dict() for inc in self._incidents],
            **self._attributs_specifiques(),
        }

    def _attributs_specifiques(self) -> dict:
        """À surcharger par les classes filles pour ajouter leurs attributs propres."""
        return {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.nom}, {self.adresse_ip}, {self.etat.value})"


class Routeur(EquipementBase):
    """Routeur réseau : gère un nombre d'interfaces et un protocole de routage."""

    PROTOCOLES_VALIDES = {"statique", "rip", "ospf", "bgp"}

    def __init__(self, nom: str, adresse_ip: str, nombre_interfaces: int = 4) -> None:
        super().__init__(nom, adresse_ip, TypeEquipement.ROUTEUR)
        if nombre_interfaces <= 0:
            raise ValueError("Un routeur doit avoir au moins une interface.")
        self.nombre_interfaces: int = nombre_interfaces
        self.protocole_routage: str = "statique"

    def ping(self) -> bool:
        return self.etat not in (EtatEquipement.EN_PANNE, EtatEquipement.INACTIF)

    def configurer(self, **parametres) -> None:
        """Configure le protocole de routage (ex : 'ospf', 'rip', 'statique', 'bgp')."""
        protocole = parametres.get("protocole_routage")
        if protocole is None:
            return
        if protocole not in self.PROTOCOLES_VALIDES:
            raise ValueError(
                f"Protocole de routage invalide : '{protocole}'. Valeurs possibles : {self.PROTOCOLES_VALIDES}."
            )
        self.protocole_routage = protocole
        logger.info("Routeur %s reconfiguré avec le protocole %s", self.nom, protocole)

    def _attributs_specifiques(self) -> dict:
        return {"nombre_interfaces": self.nombre_interfaces, "protocole_routage": self.protocole_routage}


class Switch(EquipementBase):
    """Switch réseau : gère un nombre de ports et une liste de VLANs configurés."""

    def __init__(self, nom: str, adresse_ip: str, nombre_ports: int = 24) -> None:
        super().__init__(nom, adresse_ip, TypeEquipement.SWITCH)
        if nombre_ports <= 0:
            raise ValueError("Un switch doit avoir au moins un port.")
        self.nombre_ports: int = nombre_ports
        self.vlans: List[int] = []

    def ping(self) -> bool:
        return self.etat not in (EtatEquipement.EN_PANNE, EtatEquipement.INACTIF)

    def configurer(self, **parametres) -> None:
        """Ajoute un ou plusieurs VLANs à la configuration du switch."""
        vlans = parametres.get("vlans")
        if not vlans:
            return
        for vlan_id in vlans:
            if not isinstance(vlan_id, int) or not (1 <= vlan_id <= 4094):
                raise ValueError(f"Identifiant de VLAN invalide : '{vlan_id}' (attendu entre 1 et 4094).")
            if vlan_id not in self.vlans:
                self.vlans.append(vlan_id)
        logger.info("Switch %s configuré avec les VLANs %s", self.nom, self.vlans)

    def _attributs_specifiques(self) -> dict:
        return {"nombre_ports": self.nombre_ports, "vlans": self.vlans}


class Firewall(EquipementBase):
    """Firewall réseau : gère une politique par défaut et une liste de règles."""

    POLITIQUES_VALIDES = {"allow", "deny"}

    def __init__(self, nom: str, adresse_ip: str, politique_defaut: str = "deny") -> None:
        super().__init__(nom, adresse_ip, TypeEquipement.FIREWALL)
        if politique_defaut not in self.POLITIQUES_VALIDES:
            raise ValueError(
                f"Politique par défaut invalide : '{politique_defaut}'. Valeurs possibles : {self.POLITIQUES_VALIDES}."
            )
        self.politique_defaut: str = politique_defaut
        self.regles: List[str] = []

    def ping(self) -> bool:
        return self.etat not in (EtatEquipement.EN_PANNE, EtatEquipement.INACTIF)

    def configurer(self, **parametres) -> None:
        """Ajoute une règle de filtrage (ex : 'allow tcp/443 from any')."""
        regle = parametres.get("regle")
        if not regle:
            return
        if not regle.strip():
            raise ValueError("Une règle de firewall ne peut pas être vide.")
        self.regles.append(regle.strip())
        logger.info("Firewall %s : règle ajoutée -> %s", self.nom, regle)

    def _attributs_specifiques(self) -> dict:
        return {"politique_defaut": self.politique_defaut, "regles": self.regles}


class PointAcces(EquipementBase):
    """Point d'accès Wi-Fi : gère un SSID et une bande de fréquence."""

    BANDES_VALIDES = {"2.4GHz", "5GHz", "6GHz"}

    def __init__(self, nom: str, adresse_ip: str, ssid: str, bande_frequence: str = "2.4GHz") -> None:
        super().__init__(nom, adresse_ip, TypeEquipement.POINT_ACCES)
        if not ssid or not ssid.strip():
            raise ValueError("Le SSID d'un point d'accès ne peut pas être vide.")
        if bande_frequence not in self.BANDES_VALIDES:
            raise ValueError(
                f"Bande de fréquence invalide : '{bande_frequence}'. Valeurs possibles : {self.BANDES_VALIDES}."
            )
        self.ssid: str = ssid.strip()
        self.bande_frequence: str = bande_frequence

    def ping(self) -> bool:
        return self.etat not in (EtatEquipement.EN_PANNE, EtatEquipement.INACTIF)

    def configurer(self, **parametres) -> None:
        """Modifie le SSID et/ou la bande de fréquence du point d'accès."""
        nouveau_ssid = parametres.get("ssid")
        nouvelle_bande = parametres.get("bande_frequence")
        if nouveau_ssid:
            self.ssid = nouveau_ssid.strip()
        if nouvelle_bande:
            if nouvelle_bande not in self.BANDES_VALIDES:
                raise ValueError(
                    f"Bande de fréquence invalide : '{nouvelle_bande}'. Valeurs possibles : {self.BANDES_VALIDES}."
                )
            self.bande_frequence = nouvelle_bande
        logger.info("Point d'accès %s reconfiguré (SSID=%s, bande=%s)", self.nom, self.ssid, self.bande_frequence)

    def _attributs_specifiques(self) -> dict:
        return {"ssid": self.ssid, "bande_frequence": self.bande_frequence}


# Fabrique utilisée par la persistance JSON pour recréer le bon type concret
FABRIQUE_EQUIPEMENTS = {
    TypeEquipement.ROUTEUR.value: Routeur,
    TypeEquipement.SWITCH.value: Switch,
    TypeEquipement.FIREWALL.value: Firewall,
    TypeEquipement.POINT_ACCES.value: PointAcces,
}


# ---------------------------------------------------------------------------
# Site (agrégation d'équipements)
# ---------------------------------------------------------------------------
# Un site regroupe des équipements déjà créés, sans en devenir le propriétaire.
# Cette aggregation montre que le site organise les équipements mais ne contrôle
# pas leur cycle de vie, contrairement à la composition utilisée pour les incidents.

class Site:
    """Représente un site physique de l'entreprise hébergeant des équipements.

    Relation d'agrégation : les équipements sont créés indépendamment (en
    dehors du Site) puis ajoutés via `ajouter_equipement()`. Le Site ne
    possède pas leur cycle de vie.
    """

    def __init__(self, nom: str, ville: str) -> None:
        if not nom or not nom.strip():
            raise ValueError("Le nom du site ne peut pas être vide.")
        if not ville or not ville.strip():
            raise ValueError("La ville du site ne peut pas être vide.")
        self.nom: str = nom.strip()
        self.ville: str = ville.strip()
        self._equipements: List[EquipementBase] = []
        logger.info("Site créé : %s (%s)", self.nom, self.ville)

    def ajouter_equipement(self, equipement: EquipementBase) -> None:
        """Ajoute un équipement existant à ce site (agrégation)."""
        if any(e.nom == equipement.nom for e in self._equipements):
            raise ValueError(
                f"Un équipement nommé '{equipement.nom}' existe déjà sur le site '{self.nom}'."
            )
        self._equipements.append(equipement)
        logger.info("Équipement %s ajouté au site %s", equipement.nom, self.nom)

    def retirer_equipement(self, nom_equipement: str) -> EquipementBase:
        """Retire un équipement du site sans le détruire (agrégation)."""
        equipement = self.trouver_equipement(nom_equipement)
        self._equipements.remove(equipement)
        return equipement

    def trouver_equipement(self, nom_equipement: str) -> EquipementBase:
        """Recherche un équipement par son nom sur ce site."""
        for equipement in self._equipements:
            if equipement.nom == nom_equipement:
                return equipement
        raise EquipementIntrouvableError(nom_equipement)

    @property
    def equipements(self) -> List[EquipementBase]:
        """Copie de la liste des équipements du site."""
        return list(self._equipements)

    def equipements_en_panne(self) -> List[EquipementBase]:
        """Retourne les équipements du site actuellement en panne."""
        return [e for e in self._equipements if e.etat == EtatEquipement.EN_PANNE]

    def rapport_etat(self) -> dict:
        """Construit un petit rapport de synthèse de l'état du site."""
        total = len(self._equipements)
        actifs = sum(1 for e in self._equipements if e.etat == EtatEquipement.ACTIF)
        en_panne = len(self.equipements_en_panne())
        maintenance = sum(1 for e in self._equipements if e.etat == EtatEquipement.MAINTENANCE)
        return {
            "site": self.nom, "ville": self.ville, "total_equipements": total,
            "actifs": actifs, "en_panne": en_panne, "en_maintenance": maintenance,
        }

    def __repr__(self) -> str:
        return f"Site({self.nom}, {self.ville}, {len(self._equipements)} équipements)"


# ---------------------------------------------------------------------------
# Parc (regroupe les sites)
# ---------------------------------------------------------------------------
# Le parc représente la vue globale de l'infrastructure. Il centralise les sites
# et fournit des opérations utiles pour analyser l'ensemble du réseau.

class Parc:
    """Représente le parc informatique complet (tous les sites de l'entreprise)."""

    def __init__(self, nom_entreprise: str) -> None:
        if not nom_entreprise or not nom_entreprise.strip():
            raise ValueError("Le nom de l'entreprise ne peut pas être vide.")
        self.nom_entreprise: str = nom_entreprise.strip()
        self._sites: List[Site] = []

    def ajouter_site(self, site: Site) -> None:
        """Ajoute un site au parc."""
        if any(s.nom == site.nom for s in self._sites):
            raise ValueError(f"Un site nommé '{site.nom}' existe déjà dans le parc.")
        self._sites.append(site)
        logger.info("Site %s ajouté au parc %s", site.nom, self.nom_entreprise)

    def trouver_site(self, nom_site: str) -> Site:
        """Recherche un site par son nom."""
        for site in self._sites:
            if site.nom == nom_site:
                return site
        raise ValueError(f"Aucun site '{nom_site}' trouvé dans le parc.")

    @property
    def sites(self) -> List[Site]:
        return list(self._sites)

    def rapport_global(self) -> List[dict]:
        """Rapport d'état pour tous les sites du parc."""
        return [site.rapport_etat() for site in self._sites]

    def tous_les_equipements(self) -> Iterator[Tuple[Site, EquipementBase]]:
        """Génère (site, équipement) pour tous les équipements de tous les sites."""
        for site in self._sites:
            for equipement in site.equipements:
                yield site, equipement

    def equipements_en_alerte(self, jours: int = 7, seuil: int = 3) -> List[Tuple[str, str, int]]:
        """Détecte les équipements ayant dépassé un seuil d'incidents sur une période (bonus)."""
        alertes: List[Tuple[str, str, int]] = []
        for site, equipement in self.tous_les_equipements():
            nb = equipement.nombre_incidents_sur_periode(jours)
            if nb >= seuil:
                alertes.append((site.nom, equipement.nom, nb))
        return alertes

    def __repr__(self) -> str:
        return f"Parc({self.nom_entreprise}, {len(self._sites)} site(s))"
