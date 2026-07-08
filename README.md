# Gestion de parc informatique réseau

Projet de fin de semestre — POO & Persistance des données
ISI Dakar — L2 RI — Sujet A — M. HAMANE — Année 2025-2026

## 1. Description du projet

Ce projet simule la gestion d'un parc informatique réseau réparti sur plusieurs
sites d'entreprise. Chaque site héberge des équipements réseau de natures
différentes (routeurs, switchs, firewalls, points d'accès), et chaque
équipement conserve son propre historique d'incidents techniques.

Le projet met en œuvre :

- une hiérarchie orientée objet avec classe abstraite, héritage et surcharge de méthodes ;
- une relation d'**agrégation** (`Site` ↔ `Equipement`) et une relation de
  **composition** (`Equipement` ↔ `Incident`) ;
- une triple persistance : **JSON** (état complet du parc), **CSV** (export
  des incidents) et **SQLite** (deux tables liées + requêtes métier) ;
- une gestion rigoureuse des exceptions, avec exceptions personnalisées ;
- du logging pour toutes les opérations critiques (aucun `print()` de debug).

## 2. Structure du projet (volontairement compacte)

```
parc_informatique/
├── main.py            # Point d'entrée : scénario de démonstration
├── domaine.py         # Enum, exceptions, Incident, EquipementBase + 4 classes filles, Site, Parc
├── persistance.py     # Export/import JSON, export CSV, SQLite + requêtes métier, rapports
├── test_projet.py     # Tests unitaires (pytest)
├── requirements.txt
├── README.md
└── CONTRIBUTIONS.md
```

Le code est regroupé en peu de fichiers, chacun correspondant à une couche
claire de responsabilité (domaine métier / persistance / point d'entrée),
ce qui facilite la présentation et la navigation pendant la soutenance.

## 3. Architecture orientée objet (dans `domaine.py`)

```
EquipementBase (ABC)
 ├── méthodes abstraites : ping(), configurer()
 ├── Routeur        (nombre_interfaces, protocole_routage)
 ├── Switch         (nombre_ports, vlans)
 ├── Firewall       (politique_defaut, regles)
 └── PointAcces     (ssid, bande_frequence)
```

- **Agrégation** : `Site.ajouter_equipement()` reçoit un `Equipement` créé en
  dehors du site — l'équipement existe indépendamment du site qui l'héberge.
- **Composition** : `Equipement.declarer_incident()` crée lui-même ses objets
  `Incident` — un incident n'a pas de sens ni de cycle de vie hors de son équipement.
- **Enum** : `TypeEquipement`, `EtatEquipement`, `GraviteIncident`, `StatutIncident`.

## 4. Installation

```bash
git clone <url_du_depot>
cd parc_informatique
python3 -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## 5. Utilisation

### Lancer le scénario de démonstration
```bash
python3 main.py
```
Ce script crée 2 sites avec des équipements mixtes, déclare/résout des
incidents, affiche un rapport et des alertes, puis exporte/recharge en JSON,
exporte en CSV, synchronise une base SQLite et exécute les requêtes métier.
Les logs sont écrits dans `data/parc.log`.

### Lancer les tests
```bash
pytest -v
```

## 6. Exceptions personnalisées (dans `domaine.py`)

| Exception | Cas d'usage |
|---|---|
| `EquipementIntrouvableError` | Recherche d'un équipement absent d'un site |
| `AdresseIPInvalideError` | Adresse IP fournie ne respectant pas le format IPv4 |
| `IncidentDejaResoluError` | Tentative de modifier un incident déjà résolu |
| `EquipementIndisponibleError` | Opération impossible sur un équipement hors service |

## 7. Requêtes métier SQLite (dans `persistance.py`)

1. `historique_incidents_par_equipement(nom)` — historique complet d'un équipement.
2. `equipements_en_panne_par_site(nom_site)` — équipements en panne sur un site.
3. `duree_moyenne_resolution_par_equipement()` — durée moyenne de résolution (heures).
4. `nombre_incidents_par_site_et_gravite()` — répartition incidents par site/gravité.
5. `equipements_les_plus_incidentes(limite)` — top des équipements les plus incidentés.

## 8. Auteurs

Voir [`CONTRIBUTIONS.md`](./CONTRIBUTIONS.md).
