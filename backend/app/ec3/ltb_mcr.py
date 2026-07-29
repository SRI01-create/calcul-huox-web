"""
Phase 12 — Moment critique de déversement Mcr (Annexe F, §6.3.2).

Concerne uniquement les sections H et U (profils à âme ouverte susceptibles
de déverser). Pour O et X : Mcr = None (pas de déversement à vérifier).

Colonne Excel de référence
──────────────────────────
    CQ  Mcr  moment critique de déversement  (N·m)

Formule extraite (feuilles H et U, colonnes CQ — formule identique)
────────────────────────────────────────────────────────────────────
    Si ltb_config est numérique :
        Mcr = valeur saisie  (N·m)

    Sinon (configurations 1–6) :
        Mcr = C1 × (π²·E·Iz / (k·Lm)²)
              × ( √( (k/kw)²·(IW/Iz) + (k·Lm)²·G·It/(π²·E·Iz) + (C2·zG)² )
                  − C2·zG )

    avec zG en mètres (CP/1000 dans l'Excel, CP en mm).

Table des configurations (extraite de $CM$32:$CQ$37, identique H et U)
───────────────────────────────────────────────────────────────────────
    "1" / "1/m-/D+/+"   k=1.0  kw=1.0  C1=1.000  C2=2.25
    "2" / "2/m-/D+/s"   k=1.0  kw=1.0  C1=1.127  C2=1.645
    "3" / "3/m-/d-"     k=1.0  kw=1.0  C1=1.000  C2=0.0
    "4" / "4/M+/D+/+"   k=0.5  kw=0.5  C1=1.000  C2=2.25
    "5" / "5/M+/D+/s"   k=0.5  kw=0.5  C1=1.127  C2=1.645
    "6" / "6/M+/d-"     k=0.5  kw=0.5  C1=1.000  C2=0.0

Notation
────────
    Lm  : longueur entre maintiens latéraux (m) — col CM
    k   : coefficient de longueur en flexion latérale
    kw  : coefficient de longueur en gauchissement
    C1  : facteur de moment (= 1.0 pour moment uniforme)
    C2  : facteur de charge transversale
    zG  : excentricité de la charge / centre de cisaillement (m, > 0 = destabilisant)

Références normatives
─────────────────────
    NF EN 1993-1-1 §6.3.2.2, Annexe F §F.1.2 éq. F.2
    NF EN 1993-1-4 §5.2.2
"""

from __future__ import annotations

import math
from typing import Optional

_PI2 = math.pi ** 2   # π² ≈ 9.8696

# ─── Table des configurations LTB ────────────────────────────────────────────
# Extraite de $CM$32:$CQ$37 (feuilles H et U — identiques)
# Clé : code entier "1"–"6"  (ltb_config dans models.py)
# Valeurs : k, kw, C1, C2

LTB_CONFIGS: dict[str, dict] = {
    "1": {"k": 1.0, "kw": 1.0, "C1": 1.000,  "C2": 2.25},   # 1/m-/D+/+
    "2": {"k": 1.0, "kw": 1.0, "C1": 1.127,  "C2": 1.645},  # 2/m-/D+/s
    "3": {"k": 1.0, "kw": 1.0, "C1": 1.000,  "C2": 0.0},    # 3/m-/d-
    "4": {"k": 0.5, "kw": 0.5, "C1": 1.000,  "C2": 2.25},   # 4/M+/D+/+
    "5": {"k": 0.5, "kw": 0.5, "C1": 1.127,  "C2": 1.645},  # 5/M+/D+/s
    "6": {"k": 0.5, "kw": 0.5, "C1": 1.000,  "C2": 0.0},    # 6/M+/d-
}


# ─── Mcr — formule Annexe F ──────────────────────────────────────────────────

def compute_Mcr(
    Iz: float,
    It: float,
    IW: float,
    E: float,
    G: float,
    Lm: float,
    ltb_config: str,
    zG: float,
    section_type: str,
) -> Optional[float]:
    """
    Moment critique de déversement  Mcr  (N·m)  selon l'Annexe F de l'EC3.

    Paramètres
    ----------
    Iz          : moment d'inertie axe faible z (m⁴)
    It          : constante de torsion de Saint-Venant (m⁴)
    IW          : constante de gauchissement (m⁶)
    E           : module de Young (MPa)
    G           : module de cisaillement (MPa)
    Lm          : longueur entre maintiens latéraux (m) — col CM
    ltb_config  : "1"–"6" (configuration prédéfinie) ou valeur numérique
                  en N·m saisie directement (ex. "12500.0")
    zG          : excentricité de charge / centre de cisaillement (mm)
                  positif si la charge est au-dessus du centre de cisaillement
                  (cas déstabilisant) — col CP
    section_type: "H" | "U" | "O" | "X"

    Retour
    ------
    float  Mcr > 0  (N·m)    pour H et U
    None                      pour O et X (pas de déversement)

    Correspondance Excel (col CQ, formule identique H et U)
    ────────────────────────────────────────────────────────
    IF(ISNUMBER(CN), CN,
       VLOOKUP(CN,table,4) × (π²·E·Iz/(k·Lm)²)
       × ( √((k/kw)²·IW/Iz + (k·Lm)²·G·It/(π²·E·Iz) + (C2·CP/1000)²)
           − C2·CP/1000 ) )
    """
    if section_type not in ("H", "U"):
        return None

    # ── Configuration prédéfinie ("1"–"6") — à tester EN PREMIER ────────────
    # Les codes "1"–"6" seraient mal interprétés par float() comme des Mcr directs.
    if ltb_config in LTB_CONFIGS:
        cfg = LTB_CONFIGS[ltb_config]
    else:
        # ── Cas Mcr saisie directement (ex. "12500.0") ──────────────────────
        try:
            mcr_direct = float(ltb_config)
            if mcr_direct > 0:
                return mcr_direct
        except (ValueError, TypeError):
            pass
        raise ValueError(
            f"ltb_config '{ltb_config}' invalide. "
            f"Valeurs acceptées : {list(LTB_CONFIGS.keys())} ou valeur numérique Mcr > 0 en N·m"
        )
    k   = cfg["k"]
    kw  = cfg["kw"]
    C1  = cfg["C1"]
    C2  = cfg["C2"]

    E_Pa = E * 1_000_000.0
    G_Pa = G * 1_000_000.0
    zG_m = zG / 1000.0          # mm → m

    kLm  = k * Lm               # longueur de flambement latéral (m)

    # Terme principal : π²·E·Iz / (k·Lm)²  [N]
    coeff = _PI2 * E_Pa * Iz / kLm ** 2

    # Terme sous la racine :  (k/kw)²·IW/Iz  +  (k·Lm)²·G·It/(π²·E·Iz)  +  (C2·zG)²
    term_warp   = (k / kw) ** 2 * (IW / Iz)
    term_torsion = kLm ** 2 * G_Pa * It / (_PI2 * E_Pa * Iz)
    term_load   = (C2 * zG_m) ** 2
    radicand    = term_warp + term_torsion + term_load

    # Mcr = C1 × coeff × (√radicand − C2·zG)  [N·m]
    Mcr = C1 * coeff * (math.sqrt(max(0.0, radicand)) - C2 * zG_m)
    return Mcr
