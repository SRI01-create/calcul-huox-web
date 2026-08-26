"""
Phase 16 — Dispatcher : sélectionne le moteur de calcul selon le type de section.

Point d'entrée unique pour l'API (Phase 18) et les tests de validation
(Phase 25) : run_rc() prend une configuration RC et le DataFrame ALL_LC
filtré, et délègue au moteur H, U, O ou X approprié.
"""

from __future__ import annotations

import pandas as pd

from ..models import ElementLCResult, MaterialConfig, RCConfig
from . import engine_H, engine_U, engine_O, engine_X
from .engine_H import run_H
from .engine_U import run_U
from .engine_O import run_O
from .engine_X import run_X


_ENGINES = {
    "H": run_H,
    "U": run_U,
    "O": run_O,
    "X": run_X,
}

_PRECOMPUTES = {
    "H": engine_H.precompute,
    "U": engine_U.precompute,
    "O": engine_O.precompute,
    "X": engine_X.precompute,
}


def precompute_rc(rc: RCConfig, material: MaterialConfig) -> dict:
    """
    Calcule les grandeurs invariantes (section, résistances, stabilité)
    pour un RC, via le moteur correspondant à rc.section_type.

    Utilisé par results.py (Phase 17) pour construire le Format 1 (RCSummary)
    sans dépendre du DataFrame d'efforts.

    Retour
    ------
    dict — voir la docstring de precompute() dans chaque engine_*.py.
    Clés communes aux 4 moteurs : sec, classe, classe_auto, is_welded, epsilon,
    h, b, tw, tf, t, A, fy, E, G, is_ss, gM0, gM1, gM2,
    nt_rd, nc_rd, my_c, mz_c, vy_pl, vz_pl,
    Ncr_min, Nb_Rd_y, Nb_Rd_z, lambda_bar_y, lambda_bar_z, lambda_bar_max,
    Nb_Rd_TF, Mcr, Mb_Rd, lambda_bar_LT, lambda_LT0, chi_LT_val.
    shear_ok présent pour H et U uniquement (toujours True pour O, X).

    Lève
    ----
    ValueError si rc.section_type n'est pas "H", "U", "O" ou "X".
    """
    pre_fn = _PRECOMPUTES.get(rc.section_type)
    if pre_fn is None:
        raise ValueError(
            f"Type de section inconnu : '{rc.section_type}'. "
            f"Valeurs acceptées : {list(_PRECOMPUTES)}"
        )
    return pre_fn(rc, material)


def run_rc(
    rc: RCConfig,
    material: MaterialConfig,
    df: pd.DataFrame,
) -> list[ElementLCResult]:
    """
    Calcule toutes les vérifications EC3 pour un RC donné.

    Paramètres
    ----------
    rc       : configuration RC (rc.section_type ∈ {"H","U","O","X"})
    material : matériau référencé par rc.material_number
    df       : sous-ensemble de ALL_LC pour les éléments de ce RC,
               colonnes [lc_name, element_id, NEd_t, NEd_c, Fy, Fz, Mx, My, Mz]

    Retour
    ------
    list[ElementLCResult] — une entrée par ligne de df.

    Lève
    ----
    ValueError si rc.section_type n'est pas "H", "U", "O" ou "X".
    """
    engine = _ENGINES.get(rc.section_type)
    if engine is None:
        raise ValueError(
            f"Type de section inconnu : '{rc.section_type}'. "
            f"Valeurs acceptées : {list(_ENGINES)}"
        )
    return engine(rc, material, df)


def run_all(
    rc_configs: list[RCConfig],
    materials: dict[int, MaterialConfig],
    all_lc: pd.DataFrame,
) -> list[ElementLCResult]:
    """
    Calcule toutes les vérifications EC3 pour tous les RC d'une requête.

    Paramètres
    ----------
    rc_configs : liste des configurations RC (CalculationRequest.rc_configs)
    materials  : dict {material_number → MaterialConfig} (depuis
                 CalculationRequest.material_configs)
    all_lc     : DataFrame complet [element_id, rc_number, lc_name,
                 NEd_t, NEd_c, Fy, Fz, Mx, My, Mz] — issu de
                 parsers.split_axial(build_all_lc(...)) jointe avec
                 le mapping élément→RC (parse_ele_file).

    Retour
    ------
    list[ElementLCResult] — concaténation triée par (rc_number, element_id,
    lc_name) de tous les résultats de tous les RC.

    Lève
    ----
    KeyError si rc.material_number est absent de `materials`
             (ne devrait pas survenir : validé par
             CalculationRequest.validate_material_refs).
    """
    results: list[ElementLCResult] = []

    for rc in rc_configs:
        mat = materials[rc.material_number]
        df_rc = all_lc[all_lc["rc_number"] == rc.rc_number]
        results.extend(run_rc(rc, mat, df_rc))

    results.sort(key=lambda r: (r.rc_number, r.element_id, r.lc_name))
    return results
