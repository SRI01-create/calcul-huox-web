"""
Phase 16 — Fonctions et helpers partagés par les moteurs H, U, O, X.

Regroupe :
  - les combinaisons N/Nb/Mb robustes à classe 4 (résistances = None)
  - compute_stability() : enchaîne flexural_buckling → torsional_buckling
    → compute_Mcr → ltb_resistance, pour pré-calcul d'un RC quel que soit
    le type de section (H, U, O, X).

Convention de retour "None" (= "X" Excel)
─────────────────────────────────────────
    Une grandeur est None si la vérification correspondante est hors
    portée pour cette section (classe 4, cornière sans Wpl, pas de
    déversement pour O/X…). Les fonctions ci-dessous propagent ces None
    plutôt que de les confondre avec un ratio nul.
"""

from __future__ import annotations

from typing import Optional

from ..ec3.buckling_flexural import flexural_buckling
from ..ec3.buckling_torsional import torsional_buckling
from ..ec3.ltb_mcr import compute_Mcr
from ..ec3.ltb_resistance import ltb_resistance


# ─── Ratios robustes classe 4 ────────────────────────────────────────────────

def ratio_N_combined(
    NEd_t: float, NEd_c: float,
    Nt_Rd: Optional[float], Nc_Rd: Optional[float],
) -> Optional[float]:
    """
    ratio_N = MAX(NEd_t/Nt,Rd ; NEd_c/Nc,Rd).

    None si les deux résistances sont None (classe 4 → hors portée).
    Un terme est ignoré (traité comme 0) si sa résistance associée
    est None alors que l'autre est définie (cas qui ne devrait pas
    survenir en pratique : Nt,Rd et Nc,Rd ont la même condition de classe).
    """
    if Nt_Rd is None and Nc_Rd is None:
        return None
    t = NEd_t / Nt_Rd if Nt_Rd else 0.0
    c = NEd_c / Nc_Rd if Nc_Rd else 0.0
    return max(t, c)


def n_N_factor(
    NEd_t: float, NEd_c: float,
    Nt_Rd: Optional[float], Nc_Rd: Optional[float],
) -> float:
    """
    n_N = MAX(NEd_t/Nt,Rd ; NEd_c/Nc,Rd) utilisé dans les formules My,N,Rd
    (Phase 9). Résistance None (classe 4) → terme correspondant nul
    (n_N=0 ; les fonctions Mc_Rd/My_N_Rd renverront déjà None via Mc_Rd).
    """
    nt = Nt_Rd if Nt_Rd else 1e30
    nc = Nc_Rd if Nc_Rd else 1e30
    return max(NEd_t / nt, NEd_c / nc)


def ratio_Nb_flexural(
    NEd_c: float,
    Nb_Rd_y: Optional[float],
    Nb_Rd_z: Optional[float],
) -> Optional[float]:
    """
    ratio_Nb_F = NEd_c / min(Nb,Rd,y, Nb,Rd,z)   (colonne CK).

    - None si Nb,Rd,y ET Nb,Rd,z sont None (classe 4).
    - 0.0  si NEd_c = 0 (pas de compression → pas de flambement).
    - sinon NEd_c / min(des résistances disponibles).
    """
    if Nb_Rd_y is None and Nb_Rd_z is None:
        return None
    if NEd_c == 0.0:
        return 0.0
    candidates = [v for v in (Nb_Rd_y, Nb_Rd_z) if v is not None]
    return NEd_c / min(candidates)


def ratio_Nb_torsional(
    NEd_c: float,
    Nb_Rd_TF: Optional[float],
) -> Optional[float]:
    """
    ratio_Nb_TF = NEd_c / Nb,Rd,TF   (colonne CL, U uniquement).

    None si Nb,Rd,TF est None (section != U, ou classe 4).
    """
    if Nb_Rd_TF is None:
        return None
    return 0.0 if NEd_c == 0.0 else NEd_c / Nb_Rd_TF


def ratio_LTB(My_Ed: float, Mb_Rd: Optional[float]) -> Optional[float]:
    """
    ratio_Mb = |My,Ed| / Mb,Rd   (colonne CV, H et U uniquement).

    None si Mb,Rd est None (O, X, classe 4, ou λ_LT0 ≥ ... ).
    """
    if Mb_Rd is None:
        return None
    return 0.0 if My_Ed == 0.0 else abs(My_Ed) / Mb_Rd


def overall_max(*vals: Optional[float]) -> Optional[float]:
    """MAX des valeurs non-None ; None si toutes sont None."""
    clean = [v for v in vals if v is not None]
    return max(clean) if clean else None


# ─── Pré-calcul stabilité (Phases 10-13) — toutes sections ──────────────────

def compute_stability(
    *,
    A: float, Iy: float, Iz: float, It: float, IW: float,
    iy_mm: Optional[float], iz_mm: Optional[float], ym_mm: Optional[float],
    Wpl_y: Optional[float], Wel_y: float,
    b: Optional[float], h: float,
    classe: int,
    fy: float, E: float, G: float, gamma_M1: float,
    is_stainless: bool,
    L: float, cry: float, crz: float, crT: float,
    curve_y: str, curve_z: str,
    Lm: float, ltb_config: str, zG: float,
    fabrication: str,
    section_type: str,
) -> dict:
    """
    Enchaîne le pré-calcul de stabilité indépendant des efforts (NEd_c=0,
    My_Ed fictif) — Phases 10 à 13 — pour les 4 types de section.

    Pour O et X :
        - torsional_buckling retourne Nb_Rd_TF=None et
          lambda_bar_max = max(λ̄_y, λ̄_z)  (identique à Phase 10 seule)
        - compute_Mcr retourne None → ltb_resistance retourne tout None
          (Mb_Rd=None, lambda_bar_LT=None, …)

    Retour
    ------
    dict :
        Ncr_min, Nb_Rd_y, Nb_Rd_z,
        lambda_bar_y, lambda_bar_z, lambda_bar_max,
        Nb_Rd_TF,
        Mcr, Mb_Rd, lambda_bar_LT, lambda_LT0, chi_LT_val
    """
    p10 = flexural_buckling(
        A=A, Iy=Iy, Iz=Iz, classe=classe,
        fy=fy, E=E, gamma_M1=gamma_M1,
        is_stainless=is_stainless,
        L=L, cry=cry, crz=crz,
        curve_y=curve_y, curve_z=curve_z,
        NEd_c=0.0, CO=fabrication, section_type=section_type,
    )

    p11 = torsional_buckling(
        A=A, It=It, IW=IW,
        iy_mm=iy_mm or 0.0, iz_mm=iz_mm or 0.0, ym_mm=ym_mm or 0.0,
        fy=fy, E=E, G=G, gamma_M1=gamma_M1,
        is_stainless=is_stainless,
        L=L, crT=crT, curve_z=curve_z, CO=fabrication,
        Ncr_min=p10["Ncr_min"],
        lambda_bar_y=p10["lambda_bar_y"],
        lambda_bar_z=p10["lambda_bar_z"],
        ratio_Ncr=p10["ratio_Ncr"],
        NEd_c=0.0, classe=classe,
        section_type=section_type,
    )

    Mcr = compute_Mcr(
        Iz=Iz, It=It, IW=IW, E=E, G=G,
        Lm=Lm, ltb_config=ltb_config, zG=zG,
        section_type=section_type,
    )

    p13 = ltb_resistance(
        Wpl_y=Wpl_y if Wpl_y is not None else Wel_y,
        Wel_y=Wel_y, b=b or h, h=h, classe=classe,
        fy=fy, gamma_M1=gamma_M1, is_stainless=is_stainless,
        Mcr=Mcr, fabrication=fabrication, CO=fabrication,
        My_Ed=1.0,    # fictif — Mb,Rd indépendant de My,Ed
        section_type=section_type,
    )

    return {
        "Ncr_min":        p10["Ncr_min"],
        "Nb_Rd_y":        p10["Nb_Rd_y"],
        "Nb_Rd_z":        p10["Nb_Rd_z"],
        "lambda_bar_y":   p10["lambda_bar_y"],
        "lambda_bar_z":   p10["lambda_bar_z"],
        "lambda_bar_max": p11["lambda_bar_max"],
        "Nb_Rd_TF":       p11["Nb_Rd_TF"],
        "Mcr":            Mcr,
        "Mb_Rd":          p13["Mb_Rd"],
        "lambda_bar_LT":  p13["lambda_bar_LT"],
        "lambda_LT0":     p13["lambda_LT0"],
        "chi_LT_val":     p13["chi_LT_val"],
    }
