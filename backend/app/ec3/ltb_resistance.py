"""
Phase 13 — Déversement : χ_LT et Mb,Rd (§6.3.2).

Concerne H et U. Pour O et X : Mb,Rd = None (pas de déversement).

Colonnes Excel de référence (lignes 61 H/U · ligne 60 X)
──────────────────────────────────────────────────────────
    CR   ratio_Mcr   = ABS(My,Ed / Mcr)                  (critère CT)
    CS   λ̄_LT       = √(Wy·fy / Mcr)                    (élancement)
    CT   ignoré      = "oui" si CR ≤ λ_LT0² OU CS ≤ λ_LT0
    CU   Mb,Rd       = χ_LT · Wy · fy / γM1              (N·m)
    CV   ratio_LTB   = ABS(ROUNDUP(My,Ed / Mb,Rd, 2))

Formules extraites — différences H vs U
────────────────────────────────────────

  H — λ_LT0 (cols CT et CU, arg λ_LT0)
      carbon+L : MAX(0.2, 0.2 + 0.1·b/h)
      carbon+S : MAX(0.2, 0.3·b/h)
      inox     : 0.4

  H — α_LT_mod (col CU uniquement — méthode "modifiée" §6.3.2.3)
      L : MAX(0, 0.4 − 0.2·(b/h)·λ̄_LT²)
      S : MAX(0, 0.5 − 0.25·(b/h)·λ̄_LT²)
      [identique carbone et inox pour α_LT_mod]

  H — borne supérieure χ_LT
      carbon : MIN(1/λ̄², 1, 1/(Φ+√(Φ²−λ̄²)))
      inox   : MIN(1,      1, 1/(Φ+√(Φ²−λ̄²)))

  U — α_LT (fixe, pas de facteur b/h)
      carbon        : 0.76
      inox + CO="F" : 0.34
      inox + CO≠"F" : 0.76

  U — λ_LT0
      carbon : 0.2
      inox   : 0.4  (sans condition sur CO)

  U — borne supérieure χ_LT : MIN(1, 1/(Φ+√(Φ²−λ̄²)))

Wy utilisé (CS et CU)
──────────────────────
    classe 1, 2 → Wpl_y
    classe 3    → Wel_y
    classe 4    → None ("X" dans Excel)

Références normatives
─────────────────────
    NF EN 1993-1-1 §6.3.2.2, §6.3.2.3
    NF EN 1993-1-4 §5.2.2
"""

from __future__ import annotations

import math
from typing import Optional

# ─── Helpers λ_LT0 ────────────────────────────────────────────────────────────

def lambda_LT0_H(
    is_stainless: bool,
    fabrication: str,
    b: float,
    h: float,
) -> float:
    """
    Plateau λ_LT0 pour sections H (col CT et arg de CU).

    Paramètres
    ----------
    is_stainless : True pour inox
    fabrication  : "L" (laminé) | "S" (soudé)
    b            : largeur semelle (mm) — col W
    h            : hauteur totale (mm) — col V

    Règles (extraites des formules CT et CU feuille H)
    --------------------------------------------------
    inox     → 0.4
    carbon+L → MAX(0.2, 0.2 + 0.1·b/h)
    carbon+S → MAX(0.2, 0.3·b/h)
    """
    if is_stainless:
        return 0.4
    ratio = b / h
    if fabrication == "L":
        return max(0.2, 0.2 + 0.1 * ratio)
    else:  # "S"
        return max(0.2, 0.3 * ratio)


def lambda_LT0_U(is_stainless: bool) -> float:
    """
    Plateau λ_LT0 pour sections U (col CT et arg de CU).

    Règle : 0.2 (carbone) | 0.4 (inox) — pas de condition sur CO.
    """
    return 0.4 if is_stainless else 0.2


# ─── Helper α_LT ──────────────────────────────────────────────────────────────

def alpha_LT_H(
    fabrication: str,
    b: float,
    h: float,
    lambda_bar_LT: float,
) -> float:
    """
    Facteur d'imperfection modifié α_LT pour sections H (méthode §6.3.2.3).

    Formule (identique carbone et inox)
    ------------------------------------
    L : MAX(0, 0.4 − 0.2·(b/h)·λ̄²)
    S : MAX(0, 0.5 − 0.25·(b/h)·λ̄²)
    """
    ratio = b / h
    lam2  = lambda_bar_LT ** 2
    if fabrication == "L":
        return max(0.0, 0.4 - 0.2 * ratio * lam2)
    else:  # "S"
        return max(0.0, 0.5 - 0.25 * ratio * lam2)


def alpha_LT_U(is_stainless: bool, CO: str) -> float:
    """
    Facteur d'imperfection α_LT pour sections U (fixe, pas de facteur b/h).

    Règle : 0.34 si (inox ET CO="F"), sinon 0.76.
    """
    return 0.34 if (is_stainless and CO == "F") else 0.76


# ─── χ_LT via Ayrton-Perry ────────────────────────────────────────────────────

def chi_LT(
    lambda_bar_LT: float,
    alpha: float,
    lambda_LT0: float,
    cap_inverse_lam2: bool = False,
) -> float:
    """
    Facteur de réduction au déversement χ_LT (§6.3.2.2 / §6.3.2.3).

        Φ     = 0.5·(1 + α·(λ̄_LT − λ_LT0) + λ̄_LT²)
        χ_raw = 1 / (Φ + √(Φ²−λ̄_LT²))
        χ_LT  = MIN(cap, 1, χ_raw)

    avec cap = 1/λ̄_LT²  si cap_inverse_lam2=True (carbone H, §6.3.2.3)
               1           sinon

    Paramètres
    ----------
    lambda_bar_LT   : λ̄_LT
    alpha           : facteur d'imperfection (α_LT ou α_LT_mod)
    lambda_LT0      : plateau λ_LT0
    cap_inverse_lam2: True → borne sup. = 1/λ̄² (carbone H uniquement)
    """
    lam = lambda_bar_LT
    Phi = 0.5 * (1.0 + alpha * (lam - lambda_LT0) + lam ** 2)
    disc = max(0.0, Phi ** 2 - lam ** 2)
    chi_raw = 1.0 / (Phi + math.sqrt(disc))

    if cap_inverse_lam2 and lam > 0:
        cap = min(1.0 / lam ** 2, 1.0)
    else:
        cap = 1.0

    return min(cap, chi_raw)


# ─── Fonction principale ──────────────────────────────────────────────────────

def ltb_resistance(
    # Propriétés section
    Wpl_y: float,
    Wel_y: float,
    b: float,
    h: float,
    classe: int,
    # Matériau
    fy: float,
    gamma_M1: float,
    is_stainless: bool,
    # Depuis Phase 12
    Mcr: Optional[float],
    # RC
    fabrication: str,
    CO: str,
    # Effort
    My_Ed: float,
    # Type section
    section_type: str,
) -> dict:
    """
    Résistance au déversement Mb,Rd et ratio de vérification.

    Calcule les colonnes CR, CS, CT, CU, CV pour les feuilles H et U.
    Pour O et X : toutes les valeurs = None.

    Paramètres
    ----------
    Wpl_y       : module plastique axe y (m³)
    Wel_y       : module élastique axe y (m³)
    b           : largeur semelle (mm) — col W (utilisé uniquement pour H)
    h           : hauteur totale (mm) — col V (utilisé uniquement pour H)
    classe      : classe de section (1–4)
    fy          : limite d'élasticité (MPa)
    gamma_M1    : coefficient partiel γM1
    is_stainless: True pour acier inoxydable
    Mcr         : moment critique de déversement (N·m, depuis Phase 12)
    fabrication : "L" (laminé) | "S" (soudé) — col CO
    CO          : même champ, utilisé pour α_LT_U inox : "L"/"S"/"F"
    My_Ed       : moment fléchissant de calcul (N·m)
    section_type: "H" | "U" | "O" | "X"

    Retour
    ------
    dict avec les clés :

        ratio_Mcr       (float | None)     — ABS(My,Ed/Mcr)            (CR)
        lambda_bar_LT   (float | None)     — √(Wy·fy/Mcr)              (CS)
        LTB_ignored     (bool  | None)     — critère CT                 (CT)
        Mb_Rd           (float | None, N·m)— χ_LT·Wy·fy/γM1            (CU)
        ratio_LTB       (float | None)     — ABS(My,Ed/Mb,Rd)          (CV)
        lambda_LT0      (float | None)     — λ_LT0 effectif
        alpha_LT        (float | None)     — α_LT effectif
        chi_LT_val      (float | None)     — χ_LT

    Cas particuliers
    ----------------
    - section_type O ou X  → tout à None
    - classe 4            → lambda_bar_LT, Mb,Rd, ratio_LTB = None
                            (ratio_Mcr et LTB_ignored encore calculés si Mcr fourni)
    - My_Ed = 0           → ratio_Mcr = 0, LTB_ignored = True, ratio_LTB = 0.0
    - Mcr = None          → tout à None (ne devrait pas arriver pour H/U)
    """
    _none = {
        "ratio_Mcr":     None,
        "lambda_bar_LT": None,
        "LTB_ignored":   None,
        "Mb_Rd":         None,
        "ratio_LTB":     None,
        "lambda_LT0":    None,
        "alpha_LT":      None,
        "chi_LT_val":    None,
    }

    # ── Sections sans déversement ────────────────────────────────────────────
    if section_type not in ("H", "U") or Mcr is None:
        return _none

    fy_Pa = fy * 1_000_000.0

    # ── CR — ratio My,Ed / Mcr ───────────────────────────────────────────────
    r_Mcr = abs(My_Ed / Mcr)              # CR

    # ── Wy selon classe ──────────────────────────────────────────────────────
    if classe <= 2:
        Wy = Wpl_y
    elif classe == 3:
        Wy = Wel_y
    else:  # classe 4
        Wy = None

    # ── λ_LT0 ────────────────────────────────────────────────────────────────
    if section_type == "H":
        lam_LT0 = lambda_LT0_H(is_stainless, fabrication, b, h)
    else:
        lam_LT0 = lambda_LT0_U(is_stainless)

    # ── CS — λ̄_LT (None si classe 4) ────────────────────────────────────────
    if Wy is None:
        lam_LT = None
    else:
        lam_LT = math.sqrt(Wy * fy_Pa / Mcr)   # CS

    # ── CT — critère d'ignorabilité ──────────────────────────────────────────
    if lam_LT is None:
        ignored = None
    else:
        ignored = (lam_LT <= lam_LT0) or (r_Mcr <= lam_LT0 ** 2)   # CT

    # ── CU — Mb,Rd et χ_LT (None si classe 4 ou Wy absent) ─────────────────
    if Wy is None or lam_LT is None:
        Mb = None ; r_LTB = None ; alpha = None ; chi_val = None
    else:
        if section_type == "H":
            alpha     = alpha_LT_H(fabrication, b, h, lam_LT)
            use_cap   = not is_stainless          # borne 1/λ̄² pour carbone H
        else:  # U
            alpha     = alpha_LT_U(is_stainless, CO)
            use_cap   = False

        chi_val = chi_LT(lam_LT, alpha, lam_LT0, cap_inverse_lam2=use_cap)
        Mb      = chi_val * Wy * fy_Pa / gamma_M1    # CU

        # ── CV — ratio ───────────────────────────────────────────────────────
        r_LTB = 0.0 if My_Ed == 0.0 else abs(My_Ed / Mb)

    return {
        "ratio_Mcr":     r_Mcr,
        "lambda_bar_LT": lam_LT,
        "LTB_ignored":   ignored,
        "Mb_Rd":         Mb,
        "ratio_LTB":     r_LTB,
        "lambda_LT0":    lam_LT0,
        "alpha_LT":      alpha,
        "chi_LT_val":    chi_val,
    }
