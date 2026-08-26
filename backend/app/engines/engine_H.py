"""
Phase 15 — Moteur de calcul pour sections H (I/H bi-symétriques ouvertes).

Architecture
────────────
    run_H(rc, material, df) → list[ElementLCResult]

    df : DataFrame issu de split_axial(build_all_lc(…)), filtré sur rc_number courant.
         Colonnes attendues : lc_name, element_id, NEd_t, NEd_c, Fy, Fz, Mx, My, Mz

Découpage pré-calcul / par-ligne
──────────────────────────────────
    Pré-calculé (une fois par RC, invariant quel que soit le cas de charge) :
        • Propriétés section et matériau
        • Classe de section (hypothèse compression pure — conservatoire, EC3 Table 5.2)
        • Résistances pures : Nt,Rd, Nc,Rd, My,c,Rd, Mz,c,Rd, Vy,pl,Rd, Vz,pl,Rd
        • Stabilité : Ncr_y, Ncr_z, Nb,Rd,y, Nb,Rd,z, λ̄_y, λ̄_z, λ̄_max
        • Déversement : Mcr, λ̄_LT, χ_LT, Mb,Rd, λ_LT0

    Par ligne (dépend des efforts internes) :
        • τ_w, Vy,pl,T,Rd, Vz,pl,T,Rd    (Phase 8)
        • My,V,Rd, Mz,V,Rd, My,N,Rd, Mz,N,Rd, ratio_cVN    (Phase 9)
        • kyy/kyz/kzy/kzz, ratio_CW, ratio_CX    (Phase 14)
        • Tous les ratio_* → AllRatios

Correspondance colonnes Excel → AllRatios
──────────────────────────────────────────
    ratio_N    ← max(NEd_t/Nt,Rd ;  NEd_c/Nc,Rd)
    ratio_Vy   ← |Vy| / Vy,pl,Rd
    ratio_Vz   ← |Vz| / Vz,pl,Rd
    ratio_T    ← τ_w / τ_Rd   avec τ_Rd = fy/(√3·γM0)
    ratio_cy   ← |My| / My,c,Rd
    ratio_cz   ← |Mz| / Mz,c,Rd
    ratio_VyT  ← |Vy| / Vy,pl,T,Rd
    ratio_VzT  ← |Vz| / Vz,pl,T,Rd
    ratio_cVN  ← ratio_combined_H (Phase 9, BR)
    ratio_Nb_F ← NEd_c / min(Nb,Rd,y ; Nb,Rd,z)          (Phase 10, CK)
    ratio_Nb_TF← None  (flambement torsion-flexion uniquement pour U)
    ratio_Mb   ← |My| / Mb,Rd                              (Phase 13, CV)
    ratio_MNy_b← ratio_CW                                  (Phase 14, CW)
    ratio_MNz_b← ratio_CX                                  (Phase 14, CX)

Hypothèses conservatrices
──────────────────────────
    Cmy = Cmz = CmLT = 1.0   (pas encore de champ dédié dans RCConfig)
    Anet calculé si PTC ≠ "P" ; vérification de la semelle trouée intégrée.
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from ..catalogue import get_section
from ..models import (
    AllRatios, ElementLCResult, MaterialConfig, RCConfig,
)
from ..ec3.utils import epsilon, gamma_M
from ..ec3.classification import (
    section_class_H, can_ignore_shear_buckling,
    net_areas, can_ignore_tension_flange_holes,
)
from ..ec3.section_pure import Nt_Rd, Nc_Rd, Mc_Rd, Vpl_Rd
from ..ec3.torsion import tau_w_H, Vpl_T_Rd_H
from ..ec3.section_combined import (
    MV_Rd, My_N_Rd_HU, Mz_N_Rd_HU, ratio_combined_H,
)
from ..ec3.buckling_flexural import flexural_buckling
from .common import ratio_N_combined, ratio_Nb_flexural
from ..ec3.ltb_mcr import compute_Mcr
from ..ec3.ltb_resistance import ltb_resistance
from ..ec3.interaction import interaction_factors

_SQRT3 = math.sqrt(3.0)


# ─── Pré-calcul (une fois par RC) ────────────────────────────────────────────

def precompute(rc: RCConfig, mat: MaterialConfig) -> dict:
    """
    Calcule toutes les grandeurs indépendantes du cas de charge.
    Retourne un dict `pre` utilisé par _check_row().
    """
    sec   = get_section(rc.section_type, rc.designation)
    fy    = mat.fy
    E     = mat.E
    G     = mat.G
    is_ss = (mat.steel_type == "inox")
    gM0, gM1, gM2 = gamma_M(is_ss)
    eps   = epsilon(fy, E, is_ss)
    fab   = rc.fabrication   # "L" ou "S"

    # ── Géométrie ─────────────────────────────────────────────────────────
    h  = sec["h"];  b  = sec["b"]
    tw = sec["tw"]; tf = sec["tf"]
    r  = sec["r"];  d  = sec["d"]
    A  = sec["A"]
    Iy = sec["Iy"]; Iz = sec["Iz"]
    It = sec["It"]; IW = sec["IW"]
    Sw = sec["Sw"]
    Wpl_y = sec["Wpl_y"]; Wel_y = sec["Wel_y"]
    Wpl_z = sec["Wpl_z"]; Wel_z = sec["Wel_z"]
    Av_y  = sec["Av_y"];  Av_z  = sec["Av_z"]

    # ── Classification (compression pure — conservatoire) ─────────────────
    classe_auto = section_class_H(h, b, tw, tf, r, d, eps, is_ss, fab)
    # Classe manuelle (Phase 27) : remplace la classe auto-calculée si
    # renseignée par l'utilisateur. Aucune restriction n'est appliquée —
    # outil destiné à des ingénieurs responsables de leurs calculs. L'écart
    # éventuel entre classe_auto et classe est signalé via un warning non
    # bloquant (results.build_warnings), jamais bloqué ici.
    classe = int(rc.manual_section_class) if rc.manual_section_class else classe_auto

    # ── Voilement cisaillement ────────────────────────────────────────────
    shear_ok = can_ignore_shear_buckling(h, tf, tw, eps, is_ss, is_angle=False)

    # ── Aires nettes ──────────────────────────────────────────────────────
    if rc.PTC != "P" and rc.A_trou:
        na    = net_areas(A, rc.A_trou, rc.Af_trou or 0.0, tf, b)
        Anet  = na["Anet"]
        Af_net= na["Af_net"]
        ignore_tf_holes = can_ignore_tension_flange_holes(
            Af_net, rc.Af_trou or 0.0, fy, mat.fu, gM0, gM2, rc.kr)
    else:
        Anet   = A
        ignore_tf_holes = True

    # ── Résistances pures (Phase 7) ───────────────────────────────────────
    nt_rd = Nt_Rd(classe, A, Anet, fy, mat.fu, gM0, gM2, rc.PTC, rc.kr)
    nc_rd = Nc_Rd(classe, A, fy, gM0)
    my_c  = Mc_Rd(classe, Wpl_y, Wel_y, fy, gM0)
    mz_c  = Mc_Rd(classe, Wpl_z, Wel_z, fy, gM0)
    vy_pl = Vpl_Rd(Av_y, fy, gM0)
    vz_pl = Vpl_Rd(Av_z, fy, gM0)

    # ── Flambement par flexion (Phase 10) ─────────────────────────────────
    p10 = flexural_buckling(
        A=A, Iy=Iy, Iz=Iz, classe=classe,
        fy=fy, E=E, gamma_M1=gM1,
        is_stainless=is_ss,
        L=rc.L, cry=rc.cry, crz=rc.crz,
        curve_y=rc.buckling_curve_y, curve_z=rc.buckling_curve_z,
        NEd_c=0.0,     # valeurs invariantes, NEd=0 → lambda_bar, Ncr, Nb,Rd
        CO=fab, section_type="H",
    )

    # ── Déversement Mcr (Phase 12) ────────────────────────────────────────
    Mcr = compute_Mcr(
        Iz=Iz, It=It, IW=IW, E=E, G=G,
        Lm=rc.Lm, ltb_config=rc.ltb_config,
        zG=rc.zG, section_type="H",
    )

    # ── Déversement résistance (Phase 13 — My_Ed=0 pour pré-calc) ─────────
    # Mb,Rd = χ_LT × Wy × fy / γM1 est invariant (My_Ed n'entre pas)
    # On calcule avec My_Ed fictif = 1 N·m ; LTB_ignored et ratio_LTB seront
    # recalculés par-ligne.
    p13 = ltb_resistance(
        Wpl_y=Wpl_y, Wel_y=Wel_y, b=b, h=h, classe=classe,
        fy=fy, gamma_M1=gM1, is_stainless=is_ss,
        Mcr=Mcr, fabrication=fab, CO=fab,
        My_Ed=1.0,   # fictif — Mb,Rd ne dépend pas de My,Ed
        section_type="H",
    )

    return {
        # Section
        "sec": sec, "classe": classe, "classe_auto": classe_auto, "shear_ok": shear_ok,
        "is_welded": sec["is_welded"], "epsilon": eps,
        "h": h, "b": b, "tw": tw, "tf": tf, "t": None,
        "A": A, "Iy": Iy, "Iz": Iz, "It": It, "IW": IW, "Sw": Sw,
        "Wpl_y": Wpl_y, "Wel_y": Wel_y,
        "Wpl_z": Wpl_z, "Wel_z": Wel_z,
        # Matériau
        "fy": fy, "E": E, "G": G, "is_ss": is_ss,
        "gM0": gM0, "gM1": gM1, "gM2": gM2,
        # Résistances pures
        "nt_rd": nt_rd, "nc_rd": nc_rd,
        "my_c": my_c, "mz_c": mz_c,
        "vy_pl": vy_pl, "vz_pl": vz_pl,
        # Stabilité
        "Ncr_min":       p10["Ncr_min"],
        "Nb_Rd_y":       p10["Nb_Rd_y"],
        "Nb_Rd_z":       p10["Nb_Rd_z"],
        "lambda_bar_y":  p10["lambda_bar_y"],
        "lambda_bar_z":  p10["lambda_bar_z"],
        "lambda_bar_max":p10["lambda_bar_max"],
        "ratio_Nb":      p10["ratio_Nb"],    # = 0 car NEd=0 dans pré-calc
        "Nb_Rd_TF":      None,    # H : pas de flambement torsion-flexion
        # Déversement
        "Mcr":           Mcr,
        "Mb_Rd":         p13["Mb_Rd"],
        "lambda_bar_LT": p13["lambda_bar_LT"],
        "lambda_LT0":    p13["lambda_LT0"],
        "chi_LT_val":    p13["chi_LT_val"],
    }


# ─── Calcul par ligne (element × CdC) ────────────────────────────────────────

def _check_row(
    row: pd.Series,
    pre: dict,
    rc: RCConfig,
    mat: MaterialConfig,
) -> ElementLCResult:
    """
    Applique toute la chaîne EC3 sur une ligne d'efforts internes.
    """
    NEd_t = float(row["NEd_t"])
    NEd_c = float(row["NEd_c"])
    Vy    = float(row["Fy"])
    Vz    = float(row["Fz"])
    TEd   = float(row["Mx"])
    My    = float(row["My"])
    Mz    = float(row["Mz"])

    fy  = pre["fy"]; gM0 = pre["gM0"]; gM1 = pre["gM1"]
    is_ss   = pre["is_ss"]
    classe  = pre["classe"]
    tau_Rd  = fy / _SQRT3 / gM0

    # ── Phase 7 : ratios résistance section pure ──────────────────────────
    nt_rd = pre["nt_rd"]; nc_rd = pre["nc_rd"]
    my_c  = pre["my_c"];  mz_c  = pre["mz_c"]
    vy_pl = pre["vy_pl"]; vz_pl = pre["vz_pl"]

    ratio_N  = ratio_N_combined(NEd_t, NEd_c, nt_rd, nc_rd)
    ratio_cy = abs(My) / my_c if my_c else None
    ratio_cz = abs(Mz) / mz_c if mz_c else None
    ratio_vy = abs(Vy) / vy_pl if vy_pl else None
    ratio_vz = abs(Vz) / vz_pl if vz_pl else None

    # ── Phase 8 : torsion + cisaillement réduit (H) ───────────────────────
    tau_w = tau_w_H(TEd, pre["Sw"], pre["IW"], pre["tf"])
    vy_T  = Vpl_T_Rd_H(vy_pl, tau_w, fy, gM0)
    vz_T  = Vpl_T_Rd_H(vz_pl, tau_w, fy, gM0)

    ratio_T   = tau_w / tau_Rd if tau_Rd > 0 else 0.0
    ratio_vyT = abs(Vy) / vy_T if vy_T else None
    ratio_vzT = abs(Vz) / vz_T if vz_T else None

    # ── Phase 9 : section combinée ────────────────────────────────────────
    my_V = MV_Rd(my_c, Vy, vy_T, Vz, vz_T, classe)
    mz_V = MV_Rd(mz_c, Vy, vy_T, Vz, vz_T, classe)

    nt_rd_s = nt_rd if nt_rd else 1e12
    nc_rd_s = nc_rd if nc_rd else 1e12
    n_N = max(NEd_t / nt_rd_s, NEd_c / nc_rd_s)

    my_N = My_N_Rd_HU(my_V, n_N, pre["A"], pre["b"], pre["tf"])
    mz_N = Mz_N_Rd_HU(mz_V, n_N, pre["A"], pre["b"], pre["tf"])

    ratio_cVN = ratio_combined_H(
        classe, My, Mz, my_N, mz_N, my_V, mz_V, n_N)

    # ── Phase 10 : flambement par flexion ─────────────────────────────────
    Nb_y = pre["Nb_Rd_y"]; Nb_z = pre["Nb_Rd_z"]
    ratio_Nb_F = ratio_Nb_flexural(NEd_c, Nb_y, Nb_z)

    # ── Phase 13 : déversement (ratio par ligne, Mb,Rd déjà pré-calculé) ──
    # Excel arrondit toujours au centième supérieur : CV = ABS(ROUNDUP(My/Mb,Rd, 2))
    Mb_Rd = pre["Mb_Rd"]
    if Mb_Rd and abs(My) > 0:
        ratio_Mb = math.ceil(abs(My) / Mb_Rd * 100.0) / 100.0
    elif Mb_Rd:
        ratio_Mb = 0.0
    else:
        ratio_Mb = None

    # ── Phase 14 : interaction + ratios combinés ──────────────────────────
    inter = interaction_factors(
        A=pre["A"], Iy=pre["Iy"], It=pre["It"],
        Wpl_y=pre["Wpl_y"], Wel_y=pre["Wel_y"],
        Wpl_z=pre["Wpl_z"], Wel_z=pre["Wel_z"],
        b=pre["b"], h=pre["h"], classe=classe,
        fy=fy, gamma_M0=gM0, gamma_M1=gM1,
        is_stainless=is_ss,
        Ncr_min=pre["Ncr_min"],
        Nb_Rd_y=Nb_y, Nb_Rd_z=Nb_z,
        lambda_bar_max=pre["lambda_bar_max"],
        Nb_Rd_TF=None,
        lambda_bar_LT=pre["lambda_bar_LT"], Mb_Rd=Mb_Rd,
        My_c_Rd=my_c or 1e12, Mz_c_Rd=mz_c or 1e12,
        Cmy=1.0, Cmz=1.0, CmLT=1.0,
        fabrication=rc.fabrication,
        NEd_c=NEd_c, My_Ed=My, Mz_Ed=Mz,
        section_type="H",
    )

    # ── Assemblage AllRatios ──────────────────────────────────────────────
    ratios = AllRatios(
        ratio_N    = ratio_N,
        ratio_Vy   = ratio_vy,
        ratio_Vz   = ratio_vz,
        ratio_T    = ratio_T,
        ratio_cy   = ratio_cy,
        ratio_cz   = ratio_cz,
        ratio_VyT  = ratio_vyT,
        ratio_VzT  = ratio_vzT,
        ratio_cVN  = ratio_cVN,
        ratio_Nb_F = ratio_Nb_F,
        ratio_Nb_TF= None,
        ratio_Mb   = ratio_Mb,
        ratio_MNy_b= inter["ratio_CW"],
        ratio_MNz_b= inter["ratio_CX"],
    )

    # Filtrer les None pour le calcul du max
    all_vals = [v for v in [
        ratio_N, ratio_vy, ratio_vz, ratio_T,
        ratio_cy, ratio_cz, ratio_vyT, ratio_vzT,
        ratio_cVN, ratio_Nb_F, ratio_Mb,
        inter["ratio_CW"], inter["ratio_CX"],
    ] if v is not None]
    max_r = max(all_vals) if all_vals else None

    return ElementLCResult(
        lc_name      = str(row["lc_name"]),
        element_id   = int(row["element_id"]),
        rc_number    = rc.rc_number,
        section_type = rc.section_type,
        designation  = rc.designation,
        section_class= str(classe),
        NEd_t = NEd_t, NEd_c = NEd_c,
        Vy_Ed = Vy,    Vz_Ed = Vz,
        TEd   = TEd,   My_Ed = My, Mz_Ed = Mz,
        ratios       = ratios,
        max_ratio    = max_r,
        shear_buckling_ok = pre["shear_ok"],
    )


# ─── Point d'entrée public ────────────────────────────────────────────────────

def run_H(
    rc: RCConfig,
    material: MaterialConfig,
    df: pd.DataFrame,
) -> list[ElementLCResult]:
    """
    Moteur de calcul EC3 pour sections H (bi-symétriques ouvertes).

    Paramètres
    ----------
    rc       : configuration RC (désignation, L, cry, crz, Lm, ltb_config…)
    material : propriétés matériau (fy, E, G, steel_type…)
    df       : DataFrame avec colonnes lc_name, element_id,
               NEd_t, NEd_c, Fy, Fz, Mx, My, Mz
               filtré sur les éléments appartenant à ce RC.

    Retour
    ------
    list[ElementLCResult]  — une entrée par ligne du DataFrame
    """
    if df.empty:
        return []

    pre = precompute(rc, material)
    return [_check_row(row, pre, rc, material) for _, row in df.iterrows()]
