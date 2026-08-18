"""
Phase 5 — Utilitaires EC3 communs.

Fonctions partagées par tous les modules de calcul (phases 6 à 14).
Aucune dépendance vers les autres modules ec3/.

Fonctions publiques
-------------------
    epsilon(fy, E, is_stainless)            → float
    gamma_M(is_stainless)                   → tuple[γM0, γM1, γM2]
    buckling_curve_alpha(curve)             → float  (α, Table 6.1)
    chi_reduction(lambda_bar, alpha, lam0)  → float  (χ, §6.3.1.2)
    can_ignore_buckling(lambda_bar, NEd_c, Ncr) → bool  (§6.3.1.2(4))
    can_ignore_LTB(lambda_LT, lambda_LT0, My_Ed, Mcr) → bool  (§6.3.2.2(4))

Références normatives
---------------------
    NF EN 1993-1-1 §3.2.1, Table 5.2, §6.3.1.2, §6.3.2.2
    NF EN 1993-1-1 NA §6.1(1)
    NF EN 1993-1-4 §5.1, §5.2.3
    NF EN 1993-1-4 NA §5.1(2)
"""

from __future__ import annotations

import math

# ─── Constantes ───────────────────────────────────────────────────────────────

# Module de Young de référence pour le calcul de ε (NF EN 1993-1-1 Table 5.2)
_E_REF_CARBON: float = 210_000.0   # MPa

# Facteurs d'imperfection α par courbe de flambement (EC3 Table 6.1)
_ALPHA: dict[str, float] = {
    "a0": 0.13,
    "a":  0.21,
    "b":  0.34,
    "c":  0.49,
    "d":  0.76,
}

# Coefficients partiels selon les NF NA (valeurs fixées, non modifiables par l'utilisateur)
_GAMMA_CARBON    = (1.00, 1.00, 1.25)   # γM0, γM1, γM2  — NF EN 1993-1-1 NA §6.1(1)
_GAMMA_STAINLESS = (1.10, 1.10, 1.25)   # γM0, γM1, γM2  — NF EN 1993-1-4 NA §5.1(2)


# ─── ε (facteur d'élancement de référence pour la classification) ────────────

def epsilon(fy: float, E: float, is_stainless: bool) -> float:
    """
    Facteur ε utilisé pour la classification de section (Table 5.2).

    Paramètres
    ----------
    fy            : limite d'élasticité du matériau (MPa)
    E             : module de Young du matériau (MPa)
    is_stainless  : True pour acier inoxydable, False pour acier carbone

    Retour
    ------
    float ε ≥ 0

    Formules
    --------
    Carbone  : ε = √(235 / fy)                              [Table 5.2]
    Inox     : ε = √((235 / fy) × (E / E_réf_carbone))      [EN 1993-1-4 §5.1]

    Bug trouvé et corrigé le 18/08/2026 (vérification bit-à-bit contre un
    classeur de nouveaux cas test) : le ratio E/E_réf était inversé
    (E_réf/E au lieu de E/E_réf) — sans incidence sur la classe de section
    dans les ~1400 lignes inox H/U/O testées (aucune n'était assez proche
    d'un seuil de classe pour basculer), mais formule normativement fausse.
    """
    if fy <= 0:
        raise ValueError(f"fy doit être > 0, reçu : {fy}")
    if E <= 0:
        raise ValueError(f"E doit être > 0, reçu : {E}")

    if is_stainless:
        return math.sqrt(235.0 * E / (fy * _E_REF_CARBON))
    else:
        return math.sqrt(235.0 / fy)


# ─── Coefficients partiels γM ─────────────────────────────────────────────────

def gamma_M(is_stainless: bool) -> tuple[float, float, float]:
    """
    Retourne les coefficients partiels (γM0, γM1, γM2) selon la NF NA.

    Paramètres
    ----------
    is_stainless : True → EN 1993-1-4 NA ; False → EN 1993-1-1 NA

    Retour
    ------
    tuple (γM0, γM1, γM2)

    Valeurs NF NA
    -------------
    Carbone  : γM0 = 1.00, γM1 = 1.00, γM2 = 1.25
    Inox     : γM0 = 1.10, γM1 = 1.10, γM2 = 1.25
    """
    return _GAMMA_STAINLESS if is_stainless else _GAMMA_CARBON


# ─── Courbes de flambement ────────────────────────────────────────────────────

def buckling_curve_alpha(curve: str) -> float:
    """
    Facteur d'imperfection α d'une courbe de flambement (EC3 Table 6.1).

    Paramètres
    ----------
    curve : "a0" | "a" | "b" | "c" | "d"

    Retour
    ------
    float α

    Table 6.1
    ---------
    a0 → 0.13  ·  a → 0.21  ·  b → 0.34  ·  c → 0.49  ·  d → 0.76
    """
    try:
        return _ALPHA[curve.lower()]
    except KeyError:
        raise ValueError(
            f"Courbe de flambement inconnue : '{curve}'. "
            f"Valeurs acceptées : {list(_ALPHA.keys())}"
        )


# ─── Facteur de réduction χ ───────────────────────────────────────────────────

def chi_reduction(
    lambda_bar: float,
    alpha: float,
    lambda_0: float = 0.2,
) -> float:
    """
    Facteur de réduction χ par la formule d'Ayrton-Perry (§6.3.1.2 éq. 6.49).

    Utilisé pour le flambement par flexion, par torsion et flexion-torsion.
    Applicable aussi pour l'inox avec les mêmes courbes (EN 1993-1-4 §5.2.3).

    Paramètres
    ----------
    lambda_bar : élancement relatif λ̄ (sans dimension, ≥ 0)
    alpha      : facteur d'imperfection α de la courbe (via buckling_curve_alpha)
    lambda_0   : début du plateau (défaut 0.2 pour flambement par flexion)

    Retour
    ------
    float χ ∈ ]0, 1.0]

    Formule (§6.3.1.2 éq. 6.49 et 6.50)
    -------------------------------------
    Φ = 0.5 × [1 + α × (λ̄ - λ̄₀) + λ̄²]
    χ = 1 / (Φ + √(Φ² − λ̄²))  ≤ 1.0
    """
    if lambda_bar < 0:
        raise ValueError(f"lambda_bar doit être ≥ 0, reçu : {lambda_bar}")

    phi = 0.5 * (1.0 + alpha * (lambda_bar - lambda_0) + lambda_bar ** 2)
    discriminant = phi ** 2 - lambda_bar ** 2

    # Le discriminant est toujours ≥ 0 pour λ̄ ≥ 0 et α > 0
    # (démontrable analytiquement), mais on se protège numériquement
    if discriminant < 0:
        discriminant = 0.0

    chi = 1.0 / (phi + math.sqrt(discriminant))
    return min(chi, 1.0)


# ─── Critères de non-vérification ─────────────────────────────────────────────

def can_ignore_buckling(
    lambda_bar: float,
    NEd_c: float,
    Ncr: float,
) -> bool:
    """
    Retourne True si le flambement par flexion peut être ignoré (§6.3.1.2(4)).

    Condition (OR) :
        λ̄ ≤ 0.2  OU  NEd,c / Ncr ≤ 0.04

    Paramètres
    ----------
    lambda_bar : élancement relatif λ̄
    NEd_c      : effort de compression de calcul (N, ≥ 0)
    Ncr        : charge critique élastique (N, > 0)

    Retour
    ------
    bool  — True si les effets du flambement peuvent être négligés
    """
    if lambda_bar <= 0.2:
        return True
    if Ncr > 0 and NEd_c / Ncr <= 0.04:
        return True
    return False


def can_ignore_LTB(
    lambda_LT: float,
    lambda_LT0: float,
    My_Ed: float,
    Mcr: float,
) -> bool:
    """
    Retourne True si le déversement peut être ignoré (§6.3.2.2(4)).

    Condition (OR) :
        λ̄LT ≤ λ̄LT,0  OU  My,Ed / Mcr ≤ λ̄LT,0²

    Paramètres
    ----------
    lambda_LT  : élancement relatif de déversement λ̄LT
    lambda_LT0 : valeur du plateau λ̄LT,0 (calculée en Phase 13 selon NA)
    My_Ed      : moment fléchissant de calcul (N.m, ≥ 0)
    Mcr        : moment critique élastique de déversement (N.m, > 0)

    Retour
    ------
    bool  — True si le déversement peut être négligé
    """
    if lambda_LT <= lambda_LT0:
        return True
    if Mcr > 0 and My_Ed / Mcr <= lambda_LT0 ** 2:
        return True
    return False
