"""
Phase 7 — Résistance de section aux efforts purs.

Formules extraites des colonnes AV, AW, AX, AY, AZ, BA
des feuilles H / U / O / X (ligne 61 du fichier Excel).

Fonctions publiques
-------------------
    Nt_Rd(section_class, A, Anet, fy, fu, gM0, gM2, PTC, kr) → float | None
    Nc_Rd(section_class, A, fy, gM0)                          → float | None
    Mc_Rd(section_class, Wpl, Wel, fy, gM0)                   → float | None
    Vpl_Rd(Av, fy, gM0)                                       → float

Retour
------
    float : résistance en N (efforts normaux, cisaillement) ou N.m (moments)
    None  : vérification non applicable — classe 4 ou Wpl manquant (cornières)

Unités des paramètres
---------------------
    A, Anet, Av       : m²
    Wpl, Wel          : m³
    fy, fu            : MPa  (= N/mm²)
    gM0, gM2          : sans dimension
    PTC               : "P" | "T" | "C"
    kr                : sans dimension (0.9 carbone, variable inox)

Les formules sont identiques pour carbone et inox — la distinction se fait
uniquement via les valeurs de fy, gM0 (1.0 carbone, 1.1 inox) et kr.
"""

from __future__ import annotations

import math

_SQRT3 = math.sqrt(3.0)


# ─── Traction ─────────────────────────────────────────────────────────────────

def Nt_Rd(
    section_class: int,
    A:     float,
    Anet:  float,
    fy:    float,
    fu:    float,
    gM0:   float,
    gM2:   float,
    PTC:   str   = "P",
    kr:    float = 0.9,
) -> float | None:
    """
    Résistance de calcul à la traction (N).

    Source Excel : colonne AV feuilles H / U / O / X
    -------------------------------------------------
    P (pleine) :
        Nt,Rd = A · fy / γM0                             (= Nc,Rd)

    T ou C (trouée) :
        Nt,Rd = min(
            A   · fy   / γM0,                 terme 1 : gross section yield
            kr  · Anet · fu / γM2,            terme 2 : net section ultimate
            Anet· fy   / γM0                  terme 3 : net section yield
        )

    Classe 4 → None (hors portée de l'outil).
    kr = 0.9 pour acier carbone ; valeur paramétrable pour inox.
    """
    if section_class == 4:
        return None

    # Terme de référence = résistance en compression de la section brute
    Npl = A * fy * 1e6 / gM0          # N

    if PTC == "P":
        return Npl

    # Sections trouées (T ou C) : trois termes dans le MIN (formule Excel)
    t2 = kr   * Anet * fu * 1e6 / gM2
    t3 = Anet * fy * 1e6 / gM0
    return min(Npl, t2, t3)


# ─── Compression ──────────────────────────────────────────────────────────────

def Nc_Rd(
    section_class: int,
    A:   float,
    fy:  float,
    gM0: float,
) -> float | None:
    """
    Résistance de calcul à la compression (N) = résistance plastique de section.

    Source Excel : colonne AW feuilles H / U / O / X
    -------------------------------------------------
    Class 1, 2, 3 : Nc,Rd = A · fy / γM0
    Class 4       : None  (retour "X" dans Excel)

    Note : la formule ne dépend pas de la classe (classes 1-3 donnent toutes
    A·fy/γM0). La vérification de classe sert uniquement à exclure la classe 4.
    """
    if section_class == 4:
        return None
    return A * fy * 1e6 / gM0


# ─── Flexion ──────────────────────────────────────────────────────────────────

def Mc_Rd(
    section_class: int,
    Wpl: float | None,
    Wel: float | None,
    fy:  float,
    gM0: float,
) -> float | None:
    """
    Résistance de calcul en flexion (N.m).

    Applicable à My,c,Rd (passer Wpl_y, Wel_y) ET Mz,c,Rd (passer Wpl_z, Wel_z).

    Source Excel : colonnes AX (My) et AY (Mz) feuilles H / U / O / X
    -------------------------------------------------------------------
    Class 1 ou 2 : Mc,Rd = Wpl · fy / γM0
    Class 3      : Mc,Rd = Wel · fy / γM0
    Class 4      : None  ("X" dans Excel)
    Wpl = None   : None  (cornières : Wpl non disponible au catalogue)
    """
    if section_class == 4:
        return None

    if section_class in (1, 2):
        if Wpl is None:
            return None           # cornières : Wpl absent → non vérifié en flexion
        return Wpl * fy * 1e6 / gM0

    # Class 3
    if Wel is None:
        return None
    return Wel * fy * 1e6 / gM0


# ─── Cisaillement ─────────────────────────────────────────────────────────────

def Vpl_Rd(
    Av:  float,
    fy:  float,
    gM0: float,
) -> float:
    """
    Résistance de calcul au cisaillement (N).

    Applicable à Vy,pl,Rd (passer Av_y) ET Vz,pl,Rd (passer Av_z).

    Source Excel : colonnes AZ (Vy) et BA (Vz) feuilles H / U / O / X
    -------------------------------------------------------------------
    Vpl,Rd = Av · fy / (√3 · γM0)

    Note : pas de vérification de classe — le cisaillement est indépendant
    de la classe de section (pas de retour "X" pour la classe 4).
    """
    return Av * fy * 1e6 / _SQRT3 / gM0
