"""
Phase 11 — Flambement par torsion et flexion-torsion (§6.3.1.4).

Concerne uniquement les sections U (monosymétriques ouvertes : UPE, UPN, cornières L).
Pour H, O, X : aucun calcul (retour de None pour toutes les valeurs torsionnelles).

Colonnes Excel de référence (feuille U, ligne 61)
─────────────────────────────────────────────────
    CF   Ncr_T    charge critique de torsion pure                        (N)
    CG   Ncr_TF   charge critique de flexion-torsion                     (N)
    CD   λ̄_max  mis à jour = MAX(λ̄_y, λ̄_z, λ̄_T, λ̄_TF)
    CE   ignoré  mis à jour (critère sur CC + CD_updated)
    CJ   Nb,Rd,TF résistance de flambement flexion-torsion               (N)
    CL   ratio_TF NEd_c / Nb,Rd,TF

Formules extraites de la feuille U, ligne 61
────────────────────────────────────────────
    CF = (1/i₀²) × (G×It + π²×E×IW/(crT×L)²)

    CG = (1/(2β)) × ((Ncr_T+CB) − √((Ncr_T+CB)² − 4β×Ncr_T×CB))
         avec β = 1 − (ym/i₀)²
         et CB = Ncr,min = MIN(Ncr,y ; Ncr,z)   ⚠ PAS Ncr,y seul

    CJ = χ(λ̄_TF, α_TF, λ₀=0.2) × A × fy / γM1
         avec α_TF = 0.34 (inox) | α(curve_z) (carbone)
         et λ̄_TF = √(A×fy/Ncr_TF)

    ⚠ Point vérifié (Sem, confirmé CTICM, août 2026) : la référence CG61 pointe
    vers CB61 (Ncr,min, colonne définie en Phase 10 — voir buckling_flexural.py),
    pas vers une cellule Ncr,y dédiée. Vérifié bit-à-bit sur le classeur de
    référence (UPN 120, ligne 61) : réinjecter Ncr,min dans la formule CG
    reproduit exactement CG61 = 1 043 827,36 N ; réinjecter le véritable Ncr,y
    (≈ 11 788 009 N) donne une tout autre valeur. C'est cette convention côté
    Excel — non strictement l'écriture normative du §6.3.1.4, mais admise en
    pratique par les bureaux d'études et confirmée par le CTICM — qui fait foi
    ici : le code utilise donc Ncr_min (et non Ncr_y) en entrée de Ncr,TF.
    Pour les UPN/UPE c'est presque toujours l'axe faible z-z qui gouverne
    (Iz ≪ Iy), donc Ncr_min = Ncr_z dans l'immense majorité des cas.

Notation géométrique
────────────────────
    iy, iz : rayons de giration (mm) — colonnes BY et BZ dans Excel
             calculés comme √(Iy/A) et √(Iz/A) dans Excel
             disponibles directement dans le catalogue_U.csv
    ym     : distance centroïde → centre de cisaillement (mm) — colonne CA
             disponible dans le catalogue_U.csv (colonne 'ym')
    i₀_m   : rayon polaire de giration par rapport au centre de cisaillement (m)
             i₀² = iy² + iz² + ym²  (en m²)

Paramètre α_TF de la courbe de flambement (CJ)
───────────────────────────────────────────────
    if inox  → α = 0.34   (courbe 'b', fixe, extrait de la formule CJ)
    if carbone → α = α(curve_z)   (même courbe que flambement z)
    λ₀ = 0.2 dans les deux cas (hardcodé dans la formule CJ de la feuille U)

Références normatives
─────────────────────
    NF EN 1993-1-1 §6.3.1.4
    NF EN 1993-1-4 §5.2.3
"""

from __future__ import annotations

import math
from typing import Optional

from .utils import buckling_curve_alpha, chi_reduction
from .buckling_flexural import lambda_bar_flexural, lambda0_flexural


_PI2 = math.pi ** 2   # π² ≈ 9.8696


# ─── Fonctions intermédiaires ─────────────────────────────────────────────────

def polar_radius_sq(iy_mm: float, iz_mm: float, ym_mm: float) -> float:
    """
    Rayon polaire de giration au carré  i₀²  (m²), rapporté au centre
    de cisaillement (§6.3.1.4 éq. 6.53).

        i₀² = iy² + iz² + ym²     (en m²)

    Paramètres
    ----------
    iy_mm, iz_mm, ym_mm : valeurs en mm (colonnes BY, BZ, CA de l'Excel)
    """
    return (iy_mm / 1000) ** 2 + (iz_mm / 1000) ** 2 + (ym_mm / 1000) ** 2


def ncr_torsional(
    G: float,
    It: float,
    E: float,
    IW: float,
    crT: float,
    L: float,
    i0_sq_m: float,
) -> float:
    """
    Charge critique de torsion pure  Ncr,T  (N)  (§6.3.1.4 éq. 6.52).

        Ncr,T = (1/i₀²) × (G×It + π²×E×IW / (crT×L)²)

    Paramètres
    ----------
    G         : module de cisaillement (MPa)
    It        : constante de torsion de Saint-Venant (m⁴)
    E         : module de Young (MPa)
    IW        : constante de gauchissement (m⁶)
    crT       : coefficient de longueur de flambement par torsion (> 0)
    L         : longueur de la barre (m, > 0)
    i0_sq_m   : i₀² en m² (depuis polar_radius_sq)

    Retour
    ------
    float  Ncr,T ≥ 0  (N)

    Correspondance Excel (feuille U, col CF)
    ────────────────────────────────────────
    (1/((BY/1000)²+(BZ/1000)²+(CA/1000)²)) × (O×1e6×AI + π²×N×1e6×AJ/(BS×BX)²)
    """
    G_Pa = G * 1_000_000.0
    E_Pa = E * 1_000_000.0
    Lcr_T = crT * L
    return (1.0 / i0_sq_m) * (G_Pa * It + _PI2 * E_Pa * IW / Lcr_T ** 2)


def ncr_flex_torsional(
    Ncr_T: float,
    Ncr_min: float,
    ym_mm: float,
    i0_sq_m: float,
) -> float:
    """
    Charge critique de flambement flexion-torsion  Ncr,TF  (N)
    pour une section monosymétrique (§6.3.1.4 éq. 6.54).

        β   = 1 − (ym/i₀)²
        Ncr,TF = (1/(2β)) × ((Ncr,T + Ncr,min) − √(…))

    Paramètres
    ----------
    Ncr_T     : charge critique torsion pure (N)
    Ncr_min   : MIN(Ncr,y ; Ncr,z), depuis Phase 10 (N) — PAS Ncr,y seul.
                Convention Excel (col CB) reprise ici volontairement :
                voir note en tête de module (vérifiée bit-à-bit + CTICM).
    ym_mm     : distance centroïde→centre cisaillement (mm, col CA Excel)
    i0_sq_m   : i₀² en m² (depuis polar_radius_sq)

    Retour
    ------
    float  Ncr,TF ≥ 0  (N)

    Correspondance Excel (feuille U, col CG)
    ────────────────────────────────────────
    (1/(2×(1−(CA/1000/i₀)²)))×((CF+CB)−√((CF+CB)²−4×(1−(CA/1000/i₀)²)×CF×CB))
    CB = Ncr,min (Phase 10), pas une colonne Ncr,y dédiée.
    """
    ym_m  = ym_mm / 1000.0
    i0_m  = math.sqrt(i0_sq_m)
    beta  = 1.0 - (ym_m / i0_m) ** 2
    sum_  = Ncr_T + Ncr_min
    discriminant = sum_ ** 2 - 4.0 * beta * Ncr_T * Ncr_min
    # discriminant ≥ 0 par construction (Schwartz)
    return (sum_ - math.sqrt(max(0.0, discriminant))) / (2.0 * beta)


# ─── Résistance Nb,Rd,TF ─────────────────────────────────────────────────────

def Nb_Rd_torsional(
    A: float,
    fy: float,
    gamma_M1: float,
    lambda_bar_TF: float,
    curve_z: str,
    is_stainless: bool,
) -> float:
    """
    Résistance de calcul au flambement flexion-torsion  Nb,Rd,TF  (N).

        χ_TF  = chi_reduction(λ̄_TF, α_TF, λ₀=0.2)
        Nb,Rd,TF = χ_TF × A × fy / γM1

    Paramètres
    ----------
    A               : aire de la section (m²)
    fy              : limite d'élasticité (MPa)
    gamma_M1        : coefficient partiel γM1
    lambda_bar_TF   : élancement relatif de flexion-torsion λ̄_TF
    curve_z         : courbe de flambement axe z (utilisée pour carbone)
    is_stainless    : True → α_TF = 0.34 (courbe b, fixe per formule Excel)
                      False → α_TF = α(curve_z)

    Retour
    ------
    float  Nb,Rd,TF ≥ 0  (N)

    Correspondance Excel (feuille U, col CJ)
    ────────────────────────────────────────
    α = IF(DX="inox", 0.34, α(BW))
    λ₀ = 0.2  (hardcodé, contrairement aux cols CH/CI qui utilisent IF(inox,0.4,0.2))
    """
    alpha = 0.34 if is_stainless else buckling_curve_alpha(curve_z)
    chi   = chi_reduction(lambda_bar_TF, alpha, lambda_0=0.2)
    fy_Pa = fy * 1_000_000.0
    return chi * A * fy_Pa / gamma_M1


# ─── Fonction principale ──────────────────────────────────────────────────────

def torsional_buckling(
    # Propriétés section
    A: float,
    It: float,
    IW: float,
    iy_mm: float,
    iz_mm: float,
    ym_mm: float,
    # Matériau
    fy: float,
    E: float,
    G: float,
    gamma_M1: float,
    is_stainless: bool,
    # Paramètres RC
    L: float,
    crT: float,
    curve_z: str,
    CO: str,
    # Depuis Phase 10
    Ncr_min: float,
    lambda_bar_y: float,
    lambda_bar_z: float,
    ratio_Ncr: float,
    # Effort et classe
    NEd_c: float,
    classe: int,
    # Type de section
    section_type: str = "U",
) -> dict:
    """
    Flambement par torsion et flexion-torsion — §6.3.1.4.

    Calcule les colonnes CF, CG, CJ, CL et met à jour CD et CE de la feuille U.
    Pour H, O, X : retourne un dict avec toutes les valeurs torsionnelles à None.

    Paramètres
    ----------
    A               : aire de la section (m²)
    It              : constante de torsion de Saint-Venant (m⁴)
    IW              : constante de gauchissement (m⁶)
    iy_mm           : rayon de giration axe y (mm) — col BY Excel, champ 'iy' catalogue U
    iz_mm           : rayon de giration axe z (mm) — col BZ Excel, champ 'iz' catalogue U
    ym_mm           : distance centroïde→centre cisaillement (mm) — col CA, champ 'ym' catalogue U
    fy              : limite d'élasticité (MPa)
    E               : module de Young (MPa)
    G               : module de cisaillement (MPa)
    gamma_M1        : coefficient partiel γM1
    is_stainless    : True pour acier inoxydable
    L               : longueur de la barre (m)
    crT             : coefficient de longueur de flambement par torsion
    curve_z         : courbe de flambement axe z — aussi utilisée pour Nb,Rd,TF
    CO              : configuration LTB — "L" | "S" | "F"
                      (détermine λ₀ pour CE mis à jour)
    Ncr_min         : MIN(Ncr,y ; Ncr,z) depuis Phase 10 (N) — col CB Excel.
                      Injecté tel quel dans Ncr,TF (convention Excel/CTICM,
                      voir note en tête de module) ; PAS Ncr,y seul.
    lambda_bar_y    : λ̄_y depuis Phase 10
    lambda_bar_z    : λ̄_z depuis Phase 10
    ratio_Ncr       : CC depuis Phase 10 = NEd_c / Ncr_min_flexural
    NEd_c           : effort de compression (N ≥ 0)
    classe          : classe de section (1 à 4)
    section_type    : "H" | "U" | "O" | "X"

    Retour
    ------
    dict avec les clés suivantes :

        # Valeurs torsionnelles (None si section != U)
        i0_sq_m         (float | None, m²)     — i₀² = iy²+iz²+ym²
        Ncr_T           (float | None, N)       — charge critique torsion   (CF)
        Ncr_TF          (float | None, N)       — charge critique flex-tors  (CG)
        lambda_bar_T    (float | None)          — λ̄_T = √(A×fy/Ncr_T)
        lambda_bar_TF   (float | None)          — λ̄_TF = √(A×fy/Ncr_TF)
        Nb_Rd_TF        (float | None, N)       — résistance Nb,Rd,TF        (CJ)
        ratio_Nb_TF     (float | None)          — NEd_c / Nb,Rd,TF           (CL)

        # CD et CE mis à jour pour U (valeurs Phase 10 inchangées pour H/O/X)
        lambda_bar_max  (float)                 — MAX(λ̄_y, λ̄_z[, λ̄_T, λ̄_TF])
        buckling_ignored (bool)                 — critère CE mis à jour

    Cas particuliers
    ----------------
    - section_type != "U" → toutes les valeurs torsionnelles = None ;
      lambda_bar_max et buckling_ignored calculés à partir de λ̄_y et λ̄_z.
    - classe = 4 → Nb_Rd_TF = None, ratio_Nb_TF = None
    - NEd_c = 0  → ratio_Nb_TF = 0.0
    """
    # ── Sections sans flambement torsionnel ─────────────────────────────────
    if section_type != "U":
        lam0 = lambda0_flexural(is_stainless, section_type, CO)
        lam_max = max(lambda_bar_y, lambda_bar_z)
        ignored  = (lam_max <= lam0) or (ratio_Ncr <= lam0 ** 2)
        return {
            "i0_sq_m":          None,
            "Ncr_T":            None,
            "Ncr_TF":           None,
            "lambda_bar_T":     None,
            "lambda_bar_TF":    None,
            "Nb_Rd_TF":         None,
            "ratio_Nb_TF":      None,
            "lambda_bar_max":   lam_max,
            "buckling_ignored": ignored,
        }

    # ── 1. Rayon polaire de giration ─────────────────────────────────────────
    i0_sq = polar_radius_sq(iy_mm, iz_mm, ym_mm)

    # ── 2. Ncr,T — torsion pure (CF) ────────────────────────────────────────
    Ncr_T = ncr_torsional(G, It, E, IW, crT, L, i0_sq)

    # ── 3. Ncr,TF — flexion-torsion (CG) ────────────────────────────────────
    Ncr_TF = ncr_flex_torsional(Ncr_T, Ncr_min, ym_mm, i0_sq)

    # ── 4. Élancements relatifs λ̄_T et λ̄_TF ───────────────────────────────
    fy_Pa  = fy * 1_000_000.0
    lam_T  = lambda_bar_flexural(A, fy, Ncr_T)
    lam_TF = lambda_bar_flexural(A, fy, Ncr_TF)

    # ── 5. λ̄_max mis à jour pour U (CD complet) ─────────────────────────────
    lam_max = max(lambda_bar_y, lambda_bar_z, lam_T, lam_TF)

    # ── 6. Critère CE mis à jour ─────────────────────────────────────────────
    lam0    = lambda0_flexural(is_stainless, "U", CO)
    ignored = (lam_max <= lam0) or (ratio_Ncr <= lam0 ** 2)

    # ── 7. Résistance Nb,Rd,TF (CJ) ─────────────────────────────────────────
    if classe == 4:
        Nb_TF = None
        r_TF  = None
    else:
        Nb_TF = Nb_Rd_torsional(A, fy, gamma_M1, lam_TF, curve_z, is_stainless)
        r_TF  = 0.0 if NEd_c == 0.0 else NEd_c / Nb_TF         # CL

    return {
        "i0_sq_m":          i0_sq,
        "Ncr_T":            Ncr_T,
        "Ncr_TF":           Ncr_TF,
        "lambda_bar_T":     lam_T,
        "lambda_bar_TF":    lam_TF,
        "Nb_Rd_TF":         Nb_TF,
        "ratio_Nb_TF":      r_TF,
        "lambda_bar_max":   lam_max,
        "buckling_ignored": ignored,
    }
