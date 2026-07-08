"""Tests unitaires de base pour valider l'architecture du projet.

Lancer avec : pytest -v
"""

import pytest

from domaine import (
    AdresseIPInvalideError,
    EquipementIntrouvableError,
    EtatEquipement,
    GraviteIncident,
    IncidentDejaResoluError,
    Parc,
    Routeur,
    Site,
    Switch,
)


def test_creation_equipement_valide():
    routeur = Routeur("RT-01", "10.0.0.1")
    assert routeur.etat == EtatEquipement.ACTIF
    assert routeur.ping() is True


def test_adresse_ip_invalide_leve_exception():
    with pytest.raises(AdresseIPInvalideError):
        Routeur("RT-02", "999.999.999.999")


def test_agregation_site_equipement():
    site = Site("Site Test", "Dakar")
    routeur = Routeur("RT-03", "10.0.0.2")
    site.ajouter_equipement(routeur)
    assert site.trouver_equipement("RT-03") is routeur


def test_equipement_introuvable():
    site = Site("Site Test", "Dakar")
    with pytest.raises(EquipementIntrouvableError):
        site.trouver_equipement("INCONNU")


def test_composition_incident_passe_equipement_en_panne():
    switch = Switch("SW-01", "10.0.0.3")
    switch.declarer_incident("Panne totale", GraviteIncident.CRITIQUE)
    assert switch.etat == EtatEquipement.EN_PANNE
    assert len(switch.incidents) == 1


def test_resolution_incident_remet_equipement_actif():
    switch = Switch("SW-02", "10.0.0.4")
    incident = switch.declarer_incident("Panne totale", GraviteIncident.CRITIQUE)
    switch.resoudre_incident(incident.id)
    assert switch.etat == EtatEquipement.ACTIF


def test_double_resolution_incident_leve_exception():
    switch = Switch("SW-03", "10.0.0.5")
    incident = switch.declarer_incident("Petit souci", GraviteIncident.MINEURE)
    switch.resoudre_incident(incident.id)
    with pytest.raises(IncidentDejaResoluError):
        switch.resoudre_incident(incident.id)


def test_parc_rapport_global():
    parc = Parc("Entreprise Test")
    site = Site("Site A", "Dakar")
    site.ajouter_equipement(Routeur("RT-04", "10.0.0.6"))
    parc.ajouter_site(site)
    rapport = parc.rapport_global()
    assert len(rapport) == 1
    assert rapport[0]["total_equipements"] == 1
