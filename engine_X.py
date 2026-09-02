"""
Phase 16 — Moteur de calcul pour sections X (pleines Pca/Pre/Pci).

Différences vs engine_H (le plus simple des 4 moteurs)
─────────────────────────────────────────────────────────
    • Classification : section_class_X() → toujours 1 (valeur fixe Excel $U$39=1)
    • Torsion         : tau_solid_X (Timoshenko — circ. ou rectangulaire)
    • Stabilité       : pas de déversement (Mcr=None) ; pas de flambement
                         torsion-flexion (section != "U") — λ₀=0.2 toujours
                         (lambda0_flexural retombe sur le cas par défaut pour "X")
    • Section combinée: MN_Rd_X (même formule pour My et Mz : M_V,Rd·(1−n_N²))
                         et ratio_combined_X
    • Pas de trous (PTC) — sections pleines, A_trou non pertinent
    • Pas de voilement par cisaillement (AO non applicable pour X)

Architecture identique à engine_H : _precompute() une fois par RC,
_check_row() par ligne élément × cas de charge.
"""

from __future__ import annotations

import math

import pandas as pd

from ..catalogue import get_section
from ..models import AllRatios, ElementLCResult, MaterialConfig, RCConfig
from ..ec3.utils import gamma_M, epsilon
from ..ec3.classification import section_class_X
from ..ec3.section_pure import Nt_Rd, Nc_Rd, Mc_Rd, Vpl_Rd
from ..ec3.torsion import tau_solid_X, Vpl_T_Rd_UOX
from ..ec3.section_combined import MV_Rd, MN_Rd_X, ratio_combined_X
from ..ec3.interaction import interaction_factors
from .common import (
    compute_stability,
    ratio_N_combined, n_N_factor,
    ratio_Nb_flexural, ratio_LTB,
    overall_max,
)

_SQRT3 = math.sqrt(3.0)


# ─── Pré-calcul (une fois par RC) ────────────────────────────────────────────

def precompute(rc: RCConfig, mat: MaterialConfig) -> dict:
    sec   = get_section("X", rc.designation)
    fy    = mat.fy; E = mat.E; G = mat.G
    is_ss = (mat.steel_type == "inox")
    gM0, gM1, gM2 = gamma_M(is_ss)
    eps   = epsilon(fy, E, is_ss)
    fab   = rc.fabrication
    is_circular = sec["is_circular"]

    h = sec["h"]; b = sec["b"]
    A = sec["A"]
    Iy = sec["Iy"]; Iz = sec["Iz"]; It = sec["It"]
    Wpl_y = sec["Wpl_y"]; Wel_y = sec["Wel_y"]
    Wpl_z = sec["Wpl_z"]; Wel_z = sec["Wel_z"]
    Av_y  = sec["Av_y"];  Av_z  = sec["Av_z"]

    # ── Classification — toujours 1 ────────────────────────────────────────
    classe_auto = section_class_X()
    # Classe manuelle (Phase 27) — voir engine_H.precompute() pour le détail.
    # S'applique aussi à X (toujours classe 1 en auto) par cohérence.
    classe = int(rc.manual_section_class) if rc.manual_section_class else classe_auto

    # ── Résistances pures (Phase 7) — pas de trous pour sections pleines ──
    nt_rd = Nt_Rd(classe, A, A, fy, mat.fu, gM0, gM2, "P", rc.kr)
    nc_rd = Nc_Rd(classe, A, fy, gM0)
    my_c  = Mc_Rd(classe, Wpl_y, Wel_y, fy, gM0)
    mz_c  = Mc_Rd(classe, Wpl_z, Wel_z, fy, gM0)
    vy_pl = Vpl_Rd(Av_y, fy, gM0)
    vz_pl = Vpl_Rd(Av_z, fy, gM0)

    # ── Stabilité (Phases 10-13) — pas de déversement ni de flex-torsion ──
    stab = compute_stability(
        A=A, Iy=Iy, Iz=Iz, It=It, IW=0.0,
        iy_mm=None, iz_mm=None, ym_mm=None,
        Wpl_y=Wpl_y, Wel_y=Wel_y,
        b=b, h=h, classe=classe,
        fy=fy, E=E, G=G, gamma_M1=gM1, is_stainless=is_ss,
        L=rc.L, cry=rc.cry, crz=rc.crz, crT=rc.crT,
        curve_y=rc.buckling_curve_y, curve_z=rc.buckling_curve_z,
        Lm=rc.Lm, ltb_config=rc.ltb_config, zG=rc.zG,
        fabrication=fab, section_type="X",
    )

    return {
        "sec": sec, "classe": classe, "classe_auto": classe_auto, "is_circular": is_circular,
        "is_welded": sec["is_welded"], "epsilon": eps,
        "h": h, "b": b, "t": None, "tw": None, "tf": None,
        "A": A, "Iy": Iy, "Iz": Iz, "It": It,
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

    # ── Phase 8 : torsion de Timoshenko ─────────────────────────────────────
    tau = tau_solid_X(TEd, pre["h"], pre["b"], pre["is_circular"])
    vy_T = Vpl_T_Rd_UOX(vy_pl, tau, fy, gM0)
    vz_T = Vpl_T_Rd_UOX(vz_pl, tau, fy, gM0)

    ratio_T   = tau / tau_Rd if tau_Rd > 0 else 0.0
    ratio_vyT = abs(Vy) / vy_T if vy_T else None
    ratio_vzT = abs(Vz) / vz_T if vz_T else None

    # ── Phase 9 : section combinée (même formule My et Mz pour X) ──────────
    my_V = MV_Rd(my_c, Vy, vy_T, Vz, vz_T, classe)
    mz_V = MV_Rd(mz_c, Vy, vy_T, Vz, vz_T, classe)
    n_N  = n_N_factor(NEd_t, NEd_c, nt_rd, nc_rd)
    my_N = MN_Rd_X(my_V, n_N)
    mz_N = MN_Rd_X(mz_V, n_N)

    ratio_cVN = ratio_combined_X(My, Mz, my_N, mz_N, my_V, mz_V, n_N)

    # ── Phase 10 : flambement par flexion (pas de torsion-flexion pour X) ──
    ratio_Nb_F = ratio_Nb_flexural(NEd_c, pre["Nb_Rd_y"], pre["Nb_Rd_z"])

    # ── Phase 13 : pas de déversement pour X ────────────────────────────────
    ratio_Mb = ratio_LTB(My, pre["Mb_Rd"])    # toujours None (Mb_Rd=None)

    # ── Phase 14 : interaction + ratios combinés ────────────────────────────
    inter = interaction_factors(
        A=pre["A"], Iy=pre["Iy"], It=pre["It"],
        Wpl_y=pre["Wpl_y"], Wel_y=pre["Wel_y"],
        Wpl_z=pre["Wpl_z"], Wel_z=pre["Wel_z"],
        b=pre["b"] or pre["h"], h=pre["h"], classe=classe,
        fy=fy, gamma_M0=gM0, gamma_M1=pre["gM1"], is_stainless=pre["is_ss"],
        Ncr_min=pre["Ncr_min"],
        Nb_Rd_y=pre["Nb_Rd_y"], Nb_Rd_z=pre["Nb_Rd_z"],
        lambda_bar_max=pre["lambda_bar_max"],
        Nb_Rd_TF=None,
        lambda_bar_LT=None, Mb_Rd=None,
        My_c_Rd=my_c or 1e30, Mz_c_Rd=mz_c or 1e30,
        Cmy=1.0, Cmz=1.0, CmLT=1.0,
        fabrication=rc.fabrication,
        NEd_c=NEd_c, My_Ed=My, Mz_Ed=Mz,
        section_type="X",
    )

    ratios = AllRatios(
        ratio_N=ratio_N, ratio_Vy=ratio_vy, ratio_Vz=ratio_vz,
        ratio_T=ratio_T, ratio_cy=ratio_cy, ratio_cz=ratio_cz,
        ratio_VyT=ratio_vyT, ratio_VzT=ratio_vzT, ratio_cVN=ratio_cVN,
        ratio_Nb_F=ratio_Nb_F, ratio_Nb_TF=None,
        ratio_Mb=ratio_Mb,
        ratio_MNy_b=inter["ratio_CW"], ratio_MNz_b=inter["ratio_CX"],
    )

    max_r = overall_max(
        ratio_N, ratio_vy, ratio_vz, ratio_T, ratio_cy, ratio_cz,
        ratio_vyT, ratio_vzT, ratio_cVN,
        ratio_Nb_F, ratio_Mb,
        inter["ratio_CW"], inter["ratio_CX"],
    )

    return ElementLCResult(
        lc_name=str(row["lc_name"]), element_id=int(row["element_id"]),
        rc_number=rc.rc_number, section_type=rc.section_type,
        designation=rc.designation, section_class=str(classe),
        is_circular=pre["is_circular"],
        NEd_t=NEd_t, NEd_c=NEd_c, Vy_Ed=Vy, Vz_Ed=Vz,
        TEd=TEd, My_Ed=My, Mz_Ed=Mz,
        ratios=ratios, max_ratio=max_r,
        shear_buckling_ok=True,   # AO non applicable pour X (REPRISE.md)
    )


# ─── Point d'entrée public ────────────────────────────────────────────────────

def run_X(rc: RCConfig, material: MaterialConfig, df: pd.DataFrame) -> list[ElementLCResult]:
    """
    Moteur de calcul EC3 pour sections pleines X (Pca, Pre, Pci).

    Signature et conventions identiques à run_H (Phase 15).
    """
    if df.empty:
        return []
    pre = precompute(rc, material)
    return [_check_row(row, pre, rc) for _, row in df.iterrows()]
