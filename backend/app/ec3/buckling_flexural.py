"""
Phase 10 — Flambement par flexion (§6.3.1 NF EN 1993-1-1).

Colonnes Excel de référence (lignes 61 H/U/O · ligne 60 X) :
────────────────────────────────────────────────────────────
    CB  Ncr_min   = MIN(Ncr_y, Ncr_z)                          (N)
    CC  ratio_Ncr = NEd_c / Ncr_min
    CD  λ̄_max    = MAX(λ̄_y, λ̄_z)   — partiel pour U (Phase 11
                   ajoutera les termes torsionnels CF/CG)
    CE  ignoré   = "oui" si NEd_c/Ncr_min ≤ λ₀² OU λ̄_max ≤ λ₀
    CH  Nb_Rd_y  = χ_y × A × fy / γM1                         (N)
    CI  Nb_Rd_z  = χ_z × A × fy / γM1                         (N)
    CK  ratio_Nb = NEd_c / min(Nb_Rd_y, Nb_Rd_z)

Paramètre λ₀ (plateau Ayrton-Perry + critère d'ignorabilité)
────────────────────────────────────────────────────────────
    H, X   → λ₀ = 0.2  (formule Excel carbone ; même règle si inox)
    O      → λ₀ = 0.4 si inox, sinon 0.2   (feuille O, col CE)
    U      → λ₀ = 0.4 si (inox ET CO = "F"), sinon 0.2
             (feuille U, col CE : IF(AND(DX="inox",CO="F"),0.4,0.2))

Classe de section
────────────────
    Classe 4 → Nb_Rd_y = Nb_Rd_z = ratio_Nb = None  (noté "X" dans Excel)
    Classe 1, 2, 3 → calcul complet (χ sur A × fy)

Références normatives
────────────────────
    NF EN 1993-1-1 §6.3.1.1, §6.3.1.2, §6.3.1.3
    NF EN 1993-1-4 §5.2.3

Fonctions publiques
───────────────────
    lambda0_flexural(is_stainless, section_type, CO)  → float  (λ₀)
    ncr_euler(E, I, cr, L)                            → float  (Ncr, N)
    lambda_bar_flexural(A, fy, Ncr)                   → float  (λ̄)
    Nb_Rd_flexural(A, fy, gamma_M1, lambda_bar,
                   curve, lambda_0)                   → float | None  (N)
    flexural_buckling(...)                             → dict
"""

from __future__ import annotations

import math
from typing import Optional

from .utils import buckling_curve_alpha, chi_reduction


# ─── Constante ────────────────────────────────────────────────────────────────

_PI2 = math.pi ** 2   # π² ≈ 9.8696


# ─── Paramètre λ₀ ─────────────────────────────────────────────────────────────

def lambda0_flexural(
    is_stainless: bool,
    section_type: str = "H",
    CO: str = "L",
) -> float:
    """
    Valeur du plateau λ₀ utilisée dans la formule d'Ayrton-Perry et dans le
    critère de non-vérification (§6.3.1.2(4)).

    Paramètres
    ----------
    is_stainless  : True pour acier inoxydable
    section_type  : "H" | "U" | "O" | "X"  (SectionType.value)
    CO            : configuration LTB/fabrication — "L" (laminé), "S" (soudé),
                    "F" (formé à froid, inox U et H)

    Retour
    ------
    float  0.2 ou 0.4

    Règles (extraites des formules Excel colonnes CE et CH/CI)
    ----------------------------------------------------------
    H    → 0.4 si (inox ET CO = "F"), sinon 0.2   (aligné sur U, cf. note)
    X    → 0.2  (formule Excel carbone ; applicable si inox aussi)
    O    → 0.4 si inox, sinon 0.2
    U    → 0.4 si (inox ET CO = "F"), sinon 0.2

    Correction du 19/08/2026 (Sem) : la feuille Excel H codait 0.2 en dur,
    sans le test IF(AND(DX="inox",CO="F"),0.4,0.2) présent sur la feuille U
    — confirmé erreur de construction Excel (incohérence entre feuilles
    pour un même phénomène physique), pas un choix d'ingénieur. Le code
    s'aligne désormais sur U plutôt que de reproduire l'omission d'Excel.
    Non vérifiable numériquement (RCConfig.fabrication n'autorise pas
    encore "F" côté API — cf. FabricationType, models.py — donc aucune
    ligne réelle CO="F" + inox + H n'existe dans les classeurs de test).
    """
    if not is_stainless:
        return 0.2
    # inox
    if section_type == "O":
        return 0.4
    if section_type in ("U", "H") and CO == "F":
        return 0.4
    return 0.2


# ─── Charge critique d'Euler ──────────────────────────────────────────────────

def ncr_euler(
    E: float,
    I: float,
    cr: float,
    L: float,
) -> float:
    """
    Charge critique de flambement d'Euler (N).

    Formule  Ncr = π² × E × I / (cr × L)²

    Paramètres
    ----------
    E   : module de Young (MPa)
    I   : moment d'inertie (m⁴) — Iy ou Iz selon l'axe
    cr  : coefficient de longueur de flambement (adim., > 0)
    L   : longueur de la barre (m, > 0)

    Retour
    ------
    float  Ncr ≥ 0  (N)

    Correspondance Excel
    --------------------
    Ncr_y = PI()^2 * N*1e6 * AC / (BT*BS)^2
    Ncr_z = PI()^2 * N*1e6 * AF / (BU*BS)^2
    """
    if cr <= 0:
        raise ValueError(f"cr doit être > 0, reçu : {cr}")
    if L <= 0:
        raise ValueError(f"L doit être > 0, reçu : {L}")
    E_Pa = E * 1_000_000.0          # MPa → N/m²
    L_eff = cr * L                   # longueur de flambement (m)
    return _PI2 * E_Pa * I / (L_eff ** 2)


# ─── Élancement relatif ───────────────────────────────────────────────────────

def lambda_bar_flexural(
    A: float,
    fy: float,
    Ncr: float,
) -> float:
    """
    Élancement relatif de flambement par flexion λ̄ (§6.3.1.2 éq. 6.50).

    Formule  λ̄ = √(A × fy / Ncr)

    Paramètres
    ----------
    A   : aire de la section transversale (m²)
    fy  : limite d'élasticité (MPa)
    Ncr : charge critique d'Euler (N, > 0)

    Retour
    ------
    float  λ̄ ≥ 0

    Correspondance Excel
    --------------------
    (AB*L*1e6 / (PI()^2*N*1e6*AC/(BT*BS)^2))^0.5  →  √(A×fy_Pa/Ncr_y)
    """
    if Ncr <= 0:
        raise ValueError(f"Ncr doit être > 0, reçu : {Ncr}")
    fy_Pa = fy * 1_000_000.0    # MPa → N/m²
    return math.sqrt(A * fy_Pa / Ncr)


# ─── Résistance de flambement Nb,Rd ──────────────────────────────────────────

def Nb_Rd_flexural(
    A: float,
    fy: float,
    gamma_M1: float,
    lambda_bar: float,
    curve: str,
    lambda_0: float = 0.2,
) -> Optional[float]:
    """
    Résistance de calcul au flambement par flexion Nb,Rd (§6.3.1.3 éq. 6.47).

    Formule  Nb,Rd = χ × A × fy / γM1

    Paramètres
    ----------
    A           : aire de la section (m²)
    fy          : limite d'élasticité (MPa)
    gamma_M1    : coefficient partiel γM1 (1.0 pour carbone NF NA)
    lambda_bar  : élancement relatif λ̄ ≥ 0
    curve       : courbe de flambement "a0" | "a" | "b" | "c" | "d"
    lambda_0    : plateau de la formule (0.2 par défaut, 0.4 pour certains inox)

    Retour
    ------
    float  Nb,Rd ≥ 0  (N)

    Correspondance Excel (colonne CH — axe y, CI — axe z)
    ------------------------------------------------------
    MIN(1, 1/(Φ + √(Φ²-λ̄²))) × A × fy×1e6 / γM1
    avec Φ = 0.5×(1 + α×(λ̄ - λ₀) + λ̄²)
    """
    alpha = buckling_curve_alpha(curve)
    chi   = chi_reduction(lambda_bar, alpha, lambda_0)   # ≤ 1.0
    fy_Pa = fy * 1_000_000.0
    return chi * A * fy_Pa / gamma_M1


# ─── Fonction principale ──────────────────────────────────────────────────────

def flexural_buckling(
    A: float,
    Iy: float,
    Iz: float,
    classe: int,
    fy: float,
    E: float,
    gamma_M1: float,
    is_stainless: bool,
    L: float,
    cry: float,
    crz: float,
    curve_y: str,
    curve_z: str,
    NEd_c: float,
    CO: str = "L",
    section_type: str = "H",
) -> dict:
    """
    Flambement par flexion — vérification EC3 §6.3.1.

    Calcule les colonnes CB, CC, CD, CE, CH, CI, CK du tableur Excel.

    Paramètres
    ----------
    A            : aire de la section (m²)
    Iy           : moment d'inertie axe fort y (m⁴)
    Iz           : moment d'inertie axe faible z (m⁴)
    classe       : classe de section (1 à 4)
    fy           : limite d'élasticité (MPa)
    E            : module de Young (MPa)
    gamma_M1     : coefficient partiel γM1
    is_stainless : True pour acier inoxydable
    L            : longueur de la barre (m)
    cry          : coefficient de longueur de flambement axe y
    crz          : coefficient de longueur de flambement axe z
    curve_y      : courbe de flambement axe y ("a0" | "a" | "b" | "c" | "d")
    curve_z      : courbe de flambement axe z
    NEd_c        : effort de compression de calcul (N, ≥ 0)
    CO           : configuration LTB — "L" (laminé) · "S" (soudé) · "F" (inox U)
    section_type : "H" | "U" | "O" | "X"

    Retour
    ------
    dict avec les clés suivantes :

        # Intermédiaires (toujours calculés)
        Ncr_y          (float, N)       — charge critique axe fort
        Ncr_z          (float, N)       — charge critique axe faible
        Ncr_min        (float, N)       — min(Ncr_y, Ncr_z)         → col CB
        ratio_Ncr      (float)          — NEd_c / Ncr_min            → col CC
        lambda_bar_y   (float)          — élancement relatif axe y
        lambda_bar_z   (float)          — élancement relatif axe z
        lambda_bar_max (float)          — max(λ̄_y, λ̄_z)           → col CD
        lambda_0       (float)          — 0.2 ou 0.4 selon famille/matériau
        buckling_ignored (bool)         — True si flambement ignorable → col CE

        # Résistances (None si classe = 4)
        Nb_Rd_y  (float | None, N)      — résistance flambement axe y → col CH
        Nb_Rd_z  (float | None, N)      — résistance flambement axe z → col CI
        ratio_Nb (float | None)         — NEd_c / min(Nb_Rd_y, Nb_Rd_z) → col CK

    Cas particuliers
    ----------------
    - Classe 4 : Nb_Rd_y = Nb_Rd_z = ratio_Nb = None  (noté "X" dans Excel)
    - NEd_c = 0 : ratio_Ncr = 0, buckling_ignored = True, ratio_Nb = 0.0
    - Pour U sections : lambda_bar_max ne tient pas encore compte des termes
      torsionnels (Ncr_T, Ncr_TF) qui seront ajoutés en Phase 11.
    """
    # ── 1. Paramètre λ₀ ─────────────────────────────────────────────────────
    lam0 = lambda0_flexural(is_stainless, section_type, CO)

    # ── 2. Charges critiques d'Euler ────────────────────────────────────────
    Ncr_y = ncr_euler(E, Iy, cry, L)
    Ncr_z = ncr_euler(E, Iz, crz, L)
    Ncr   = min(Ncr_y, Ncr_z)                                      # CB

    # ── 3. Ratio NEd_c / Ncr  (CC) ──────────────────────────────────────────
    ratio_Ncr = NEd_c / Ncr                                         # CC

    # ── 4. Élancements relatifs (CD) ────────────────────────────────────────
    lam_y   = lambda_bar_flexural(A, fy, Ncr_y)
    lam_z   = lambda_bar_flexural(A, fy, Ncr_z)
    lam_max = max(lam_y, lam_z)                                     # CD

    # ── 5. Critère de non-vérification (CE) ─────────────────────────────────
    # §6.3.1.2(4) : λ̄ ≤ λ₀  OU  NEd_c/Ncr ≤ λ₀²
    ignored = (lam_max <= lam0) or (ratio_Ncr <= lam0 ** 2)        # CE

    # ── 6. Résistances de flambement CH, CI (None si classe 4) ─────────────
    if classe == 4:
        Nb_y = None
        Nb_z = None
        r_Nb = None
    else:
        Nb_y = Nb_Rd_flexural(A, fy, gamma_M1, lam_y, curve_y, lam0)   # CH
        Nb_z = Nb_Rd_flexural(A, fy, gamma_M1, lam_z, curve_z, lam0)   # CI

        # ── 7. Ratio CK ─────────────────────────────────────────────────────
        if NEd_c == 0.0:
            r_Nb = 0.0
        else:
            r_Nb = NEd_c / min(Nb_y, Nb_z)                             # CK

    return {
        # Intermédiaires
        "Ncr_y":            Ncr_y,
        "Ncr_z":            Ncr_z,
        "Ncr_min":          Ncr,
        "ratio_Ncr":        ratio_Ncr,
        "lambda_bar_y":     lam_y,
        "lambda_bar_z":     lam_z,
        "lambda_bar_max":   lam_max,
        "lambda_0":         lam0,
        "buckling_ignored": ignored,
        # Résistances
        "Nb_Rd_y":  Nb_y,
        "Nb_Rd_z":  Nb_z,
        "ratio_Nb": r_Nb,
    }
