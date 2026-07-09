# Contributions au projet

## Membres du groupe

- Ousmane DIENG
- Magatte SAGNA
- Serigne SALIOU MBACKE DIENG

## Répartition du travail

| | Modules / classes développés | Contribution estimée |
|--------|-------------------------------|----------------------|
| Serigne SALIOU MBACKE DIENG  | `domaine.py` : Enum, exceptions, `Incident`, `EquipementBase` + classes filles | ...% |
|Magatte Sagna |  `main.py`+ `test_projet.py` (scénario de démonstration) | ...% |
|Ousmane Dieng  | `persistance.py` (JSON, CSV, SQLite, rapports) +  | ...% |

## Répartition par phase

| Phase | Responsable principal |
|-----------------------------------|------------------------|
| Conception (diagramme de classes) | ... |
| Implémentation POO                | ... |
| Persistance fichiers (JSON/CSV)   | ... |
| Persistance SQL                   | ... |
| Tests / gestion des exceptions    | ... |
| README / documentation            | ... |

## Difficultés rencontrées et résolution
: la reconstruction des équipements
concrets depuis le JSON générique a nécessité une petite fabrique
[`FABRIQUE_EQUIPEMENTS`] dans `domaine.py`, utilisée par `persistance.py`
pour réinstancier la bonne sous-classe selon `type_equipement`.)


