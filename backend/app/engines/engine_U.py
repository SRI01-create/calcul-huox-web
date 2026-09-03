"""
Phase 16 — Moteur de calcul pour sections U (canaux UPN/UPE/PFC et cornières L).

Différences vs engine_H
─────────────────────────
    • Classification : section_class_U (gère cornières via détection "L ")
    • Torsion         : tau_mixed_U (canal : Sw_w/IW + St-Venant ; cornière : None si TEd≠0)
    • Stabilité       : torsional_buckling (Phase 11) actif → Nb,Rd,TF, λ̄_max complet
    • Déversement     : actif comme pour H (Mcr, Mb,Rd via ltb_resistance, section_type="U")
    • Section combinée: ratio_combined_U (formule linéaire en classe 1/2,
                          différente de ratio_combined_H)
    • ratio_Nb_TF     : calculé (None uniquement si classe 4)

Cornières (is_angle)
─────────────────────
    • Wpl_y = Wpl_z = None → Mc_Rd retourne None si classe ≤ 2 (jamais le cas,
      classe max = 3 pour les cornières) ; classe 3 → Mc_Rd via Wel, OK.
    • tau_mixed_U(is_angle=True) → None si TEd≠0 (vérification torsion hors
      portée), 0.0 sinon → ratio_T = None ou 0.0 en conséquence.
    • can_ignore_shear_buckling(is_angle=True) → toujours True.

Architecture identique à engine_H : _precompute() une fois par RC,
_check_row() par ligne élément × cas de charge.
"""

from __future__ import annotations

import math

import pandas as pd

from ..catalogue import get_section
from ..models import AllRatios, ElementLCResult, MaterialConfig, RCConfig
from ..ec3.utils import epsilon, gamma_M
from ..ec3.classification import (
    section_class_U, can_ignore_shear_buckling,
    net_areas, can_ignore_tension_flange_holes,
)
from ..ec3.section_pure import Nt_Rd, Nc_Rd, Mc_Rd, Vpl_Rd
from ..ec3.torsion import tau_mixed_U, Vpl_T_Rd_UOX
from ..ec3.section_combined import (
    MV_Rd, My_N_Rd_HU, Mz_N_Rd_HU, ratio_combined_U,
)
from ..ec3.interaction import interaction_factors
from .common import (
    compute_stability,
    ratio_N_combined, n_N_factor,
    ratio_Nb_flexural, ratio_Nb_torsional, ratio_LTB,
    overall_max,
)

_SQRT3 = math.sqrt(3.0)


# ─── Pré-calcul (une fois par RC) ────────────────────────────────────────────

def precompute(rc: RCConfig, mat: MaterialConfig) -> dict:
    sec   = get_section("U", rc.designation)
    fy    = mat.fy; E = mat.E; G = mat.G
    is_ss = (mat.steel_type == "inox")
    gM0, gM1, gM2 = gamma_M(is_ss)
    eps   = epsilon(fy, E, is_ss)
    fab   = rc.fabrication
    is_angle = sec["is_angle"]

    h  = sec["h"];  b  = sec["b"]
    tw = sec["tw"]; tf = sec["tf"]
    r  = sec["r"];  d  = sec["d"]
    A  = sec["A"]
    Iy = sec["Iy"]; Iz = sec["Iz"]
    It = sec["It"]; IW = sec["IW"]
    Sw_w = sec["Sw_w"]
    Wpl_y = sec["Wpl_y"]; Wel_y = sec["Wel_y"]
    Wpl_z = sec["Wpl_z"]; Wel_z = sec["Wel_z"]
    Av_y  = sec["Av_y"];  Av_z  = sec["Av_z"]
    iy_mm = sec["iy"]; iz_mm = sec["iz"]; ym_mm = sec["ym"]

    # tf_eff : pour les cornières tf peut théoriquement être absent
    # (catalogue actuel le renseigne toujours, mais on protège par sécurité)
    tf_eff = tf if tf is not None else tw

    # ── Classification ───────────────────────────────────────────────────
    classe_auto = section_class_U(h, b, tw, tf, r, d, is_angle, eps, is_ss, fab)
    # Classe manuelle (Phase 27) — voir engine_H.precompute() pour le détail.
    classe = int(rc.manual_section_class) if rc.manual_section_class else classe_auto

    # ── Voilement cisaillement ────────────────────────────────────────────
    shear_ok = can_ignore_shear_buckling(h, tf_eff, tw, eps, is_ss, is_angle)

    # ── Aires nettes ──────────────────────────────────────────────────────
    if rc.PTC != "P" and rc.A_trou:
        na    = net_areas(A, rc.A_trou, rc.Af_trou or 0.0, tf_eff, b)
        Anet  = na["Anet"]
        Af_net= na["Af_net"]
    else:
        Anet = A

    # ── Résistances pures (Phase 7) ───────────────────────────────────────
    nt_rd = Nt_Rd(classe, A, Anet, fy, mat.fu, gM0, gM2, rc.PTC, rc.kr)
    nc_rd = Nc_Rd(classe, A, fy, gM0)
    my_c  = Mc_Rd(classe, Wpl_y, Wel_y, fy, gM0)
    mz_c  = Mc_Rd(classe, Wpl_z, Wel_z, fy, gM0)
    vy_pl = Vpl_Rd(Av_y, fy, gM0)
    vz_pl = Vpl_Rd(Av_z, fy, gM0)

    # ── Stabilité (Phases 10-13) ────────────────────────────────────────────
    stab = compute_stability(
        A=A, Iy=Iy, Iz=Iz, It=It, IW=IW,
        iy_mm=iy_mm, iz_mm=iz_mm, ym_mm=ym_mm,
        Wpl_y=Wpl_y, Wel_y=Wel_y,
        b=b, h=h, classe=classe,
        fy=fy, E=E, G=G, gamma_M1=gM1, is_stainless=is_ss,
        L=rc.L, cry=rc.cry, crz=rc.crz, crT=rc.crT,
        curve_y=rc.buckling_curve_y, curve_z=rc.buckling_curve_z,
        Lm=rc.Lm, ltb_config=rc.ltb_config, zG=rc.zG,
        fabrication=fab, section_type="U",
    )

    return {
        "sec": sec, "classe": classe, "classe_auto": classe_auto,
        "shear_ok": shear_ok, "is_angle": is_angle,
        "is_welded": sec["is_welded"], "epsilon": eps,
        "h": h, "b": b, "tw": tw, "tf": tf_eff, "t": None,
        "A": A, "Iy": Iy, "Iz": Iz, "It": It, "IW": IW, "Sw_w": Sw_w,
        "Wpl_y": Wpl_y, "Wel_y": Wel_y, "Wpl_z": Wpl_z, "Wel_z": Wel_z,
        "fy": fy, "E": E, "G": G, "is_ss": is_ss,
        "gM0": gM0, "gM1": gM1, "gM2": gM2,
        "nt_rd": nt_rd, "nc_rd": nc_rd,
        "my_c": my_c, "mz_c": mz_c, "vy_pl": vy_pl, "vz_pl": vz_pl,
        **stab,
    }


# ─── Calcul par ligne ─────────────────────────────────────────────────────────

def _check_row(row: pd.Series, pre: dict, rc: RCConfig) -> ElementLCResult:
    NEd_t = float(row["NEd_t"]); NEd_c = float(row["NEd_c"])
    Vy = float(row["Fy"]); Vz = float(row["Fz"])
    TEd = float(row["Mx"]); My = float(row["My"]); Mz = float(row["Mz"])

    fy = pre["fy"]; gM0 = pre["gM0"]
    classe = pre["classe"]
    tau_Rd = fy / _SQRT3 / gM0

    nt_rd = pre["nt_rd"]; nc_rd = pre["nc_rd"]
    my_c  = pre["my_c"];  mz_c  = pre["mz_c"]
    vy_pl = pre["vy_pl"]; vz_pl = pre["vz_pl"]

    # ── Phase 7 ─────────────────────────────────────────────────────────────
    ratio_N  = ratio_N_combined(NEd_t, NEd_c, nt_rd, nc_rd)
    ratio_cy = abs(My) / my_c if my_c else None
    ratio_cz = abs(Mz) / mz_c if mz_c else None
    ratio_vy = abs(Vy) / vy_pl if vy_pl else None
    ratio_vz = abs(Vz) / vz_pl if vz_pl else None

    # ── Phase 8 : torsion mixte canal / cornière ───────────────────────────
    tau = tau_mixed_U(TEd, pre["Sw_w"], pre["IW"], pre["tw"], pre["tf"],
                      pre["It"], is_angle=pre["is_angle"])
    vy_T = Vpl_T_Rd_UOX(vy_pl, tau, fy, gM0)
    vz_T = Vpl_T_Rd_UOX(vz_pl, tau, fy, gM0)

    if tau is None:
        ratio_T = None
    else:
        ratio_T = tau / tau_Rd if tau_Rd > 0 else 0.0
    ratio_vyT = abs(Vy) / vy_T if vy_T else None
    ratio_vzT = abs(Vz) / vz_T if vz_T else None

    # ── Phase 9 : section combinée ──────────────────────────────────────────
    my_V = MV_Rd(my_c, Vy, vy_T, Vz, vz_T, classe)
    mz_V = MV_Rd(mz_c, Vy, vy_T, Vz, vz_T, classe)
    n_N  = n_N_factor(NEd_t, NEd_c, nt_rd, nc_rd)
    my_N = My_N_Rd_HU(my_V, n_N, pre["A"], pre["b"], pre["tf"])
    mz_N = Mz_N_Rd_HU(mz_V, n_N, pre["A"], pre["b"], pre["tf"])

    ratio_cVN = ratio_combined_U(
        classe, My, Mz, my_N, mz_N, my_V, mz_V, n_N)

    # ── Phase 10/11 : flambement flexion + torsion-flexion ──────────────────
    ratio_Nb_F  = ratio_Nb_flexural(NEd_c, pre["Nb_Rd_y"], pre["Nb_Rd_z"])
    ratio_Nb_TF = ratio_Nb_torsional(NEd_c, pre["Nb_Rd_TF"])

    # ── Phase 13 : déversement ──────────────────────────────────────────────
    ratio_Mb = ratio_LTB(My, pre["Mb_Rd"])

    # ── Phase 14 : interaction + ratios combinés ────────────────────────────
    inter = interaction_factors(
        A=pre["A"], Iy=pre["Iy"], It=pre["It"],
        Wpl_y=pre["Wpl_y"] or pre["Wel_y"], Wel_y=pre["Wel_y"],
        Wpl_z=pre["Wpl_z"] or pre["Wel_z"], Wel_z=pre["Wel_z"],
        b=pre["b"], h=pre["h"], classe=classe,
        fy=fy, gamma_M0=gM0, gamma_M1=pre["gM1"], is_stainless=pre["is_ss"],
        Ncr_min=pre["Ncr_min"],
        Nb_Rd_y=pre["Nb_Rd_y"], Nb_Rd_z=pre["Nb_Rd_z"],
        lambda_bar_max=pre["lambda_bar_max"],
        Nb_Rd_TF=pre["Nb_Rd_TF"],
        lambda_bar_LT=pre["lambda_bar_LT"], Mb_Rd=pre["Mb_Rd"],
        My_c_Rd=my_c or 1e30, Mz_c_Rd=mz_c or 1e30,
        Cmy=1.0, Cmz=1.0, CmLT=1.0,
        fabrication=rc.fabrication,
        NEd_c=NEd_c, My_Ed=My, Mz_Ed=Mz,
        section_type="U",
    )

    ratios = AllRatios(
        ratio_N=ratio_N, ratio_Vy=ratio_vy, ratio_Vz=ratio_vz,
        ratio_T=ratio_T, ratio_cy=ratio_cy, ratio_cz=ratio_cz,
        ratio_VyT=ratio_vyT, ratio_VzT=ratio_vzT, ratio_cVN=ratio_cVN,
        ratio_Nb_F=ratio_Nb_F, ratio_Nb_TF=ratio_Nb_TF,
        ratio_Mb=ratio_Mb,
        ratio_MNy_b=inter["ratio_CW"], ratio_MNz_b=inter["ratio_CX"],
    )

    max_r = overall_max(
        ratio_N, ratio_vy, ratio_vz, ratio_T, ratio_cy, ratio_cz,
        ratio_vyT, ratio_vzT, ratio_cVN,
        ratio_Nb_F, ratio_Nb_TF, ratio_Mb,
        inter["ratio_CW"], inter["ratio_CX"],
    )

    return ElementLCResult(
        lc_name=str(row["lc_name"]), element_id=int(row["element_id"]),
        rc_number=rc.rc_number, section_type=rc.section_type,
        designation=rc.designation, section_class=str(classe),
        is_welded=pre["is_welded"], is_angle=pre["is_angle"],
        NEd_t=NEd_t, NEd_c=NEd_c, Vy_Ed=Vy, Vz_Ed=Vz,
        TEd=TEd, My_Ed=My, Mz_Ed=Mz,
        ratios=ratios, max_ratio=max_r,
        shear_buckling_ok=pre["shear_ok"],
    )


# ─── Point d'entrée public ────────────────────────────────────────────────────

def run_U(rc: RCConfig, material: MaterialConfig, df: pd.DataFrame) -> list[ElementLCResult]:
    """
    Moteur de calcul EC3 pour sections U (canaux et cornières).

    Signature et conventions identiques à run_H (Phase 15).
    """
    if df.empty:
        return []
    pre = precompute(rc, material)
    return [_check_row(row, pre, rc) for _, row in df.iterrows()]
