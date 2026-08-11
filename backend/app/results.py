"""
Phase 17 — Compilation des résultats (Format 1 "rslt" + Format 2 "co").

Format 2 ("co" — détail) est déjà produit par dispatch.run_all() :
    list[ElementLCResult] — une ligne par combinaison élément × cas de charge.

Format 1 ("rslt" — synthèse par RC) est produit ici par build_format1() :
    pour chaque RC, regroupe
      - les propriétés de section et matériau et les résistances calculées
        (issues de dispatch.precompute_rc — invariantes par RC)
      - les efforts internes maximaux et les ratios maximaux observés sur
        tous les éléments/CdC de ce RC (agrégés depuis le Format 2)

build_response() assemble le tout en CalculationResponse, point d'entrée
unique pour l'API (Phase 18).

Correspondance avec l'Excel
────────────────────────────
    Format 1 ≈ tableau de synthèse "1 ligne par RC" (section, matériau,
        résistances AV-CV, λ, Mcr, et MAX des ratios sur toutes les lignes
        H/U/O/X de ce RC).
    Format 2 ≈ feuilles H/U/O/X elles-mêmes, une ligne par élément×CdC.
"""

from __future__ import annotations

import pandas as pd

from .models import (
    AllRatios, CalculationResponse, ElementLCResult,
    MaterialConfig, RCConfig, RCSummary,
)
from .engines.dispatch import precompute_rc, run_all


# ─── Agrégation des ratios maximaux ──────────────────────────────────────────

_RATIO_FIELDS = list(AllRatios.model_fields.keys())


def _max_ratios(rows: list[ElementLCResult]) -> AllRatios:
    """
    AllRatios où chaque champ = MAX sur `rows` de ce ratio (None ignorés).

    Si toutes les valeurs d'un champ sont None pour ce RC (vérification
    hors portée pour ce type de section/classe), le champ reste None.
    """
    maxima: dict[str, float | None] = {}
    for field in _RATIO_FIELDS:
        vals = [getattr(r.ratios, field) for r in rows]
        vals = [v for v in vals if v is not None]
        maxima[field] = max(vals) if vals else None
    return AllRatios(**maxima)


def _overall_max(ratios: AllRatios) -> float | None:
    """MAX sur tous les champs non-None de `ratios`."""
    vals = [v for v in ratios.__dict__.values() if v is not None]
    return max(vals) if vals else None


def _max_abs(rows: list[ElementLCResult], attr: str) -> float:
    """MAX(|getattr(r, attr)|) sur `rows`, 0.0 si `rows` est vide."""
    if not rows:
        return 0.0
    return max(abs(getattr(r, attr)) for r in rows)


# ─── Format 1 — synthèse par RC ───────────────────────────────────────────────

def build_rc_summary(
    rc: RCConfig,
    material: MaterialConfig,
    rows: list[ElementLCResult],
) -> RCSummary:
    """
    Construit la synthèse Format 1 d'un RC.

    Paramètres
    ----------
    rc       : configuration du RC
    material : matériau référencé par rc.material_number
    rows     : sous-ensemble de Format 2 pour ce RC
               (peut être vide si le RC n'a aucun élément dans les fichiers
               Ansys importés — les efforts/ratios max valent alors 0/None)

    Retour
    ------
    RCSummary
    """
    pre = precompute_rc(rc, material)

    max_ratios   = _max_ratios(rows)
    overall_max  = _overall_max(max_ratios)

    # shear_ok absent (O, X) → toujours True (AO non applicable, REPRISE.md)
    shear_ok = pre.get("shear_ok", True)

    return RCSummary(
        rc_number     = rc.rc_number,
        section_type  = rc.section_type,
        designation   = rc.designation,
        section_class = str(pre["classe"]),
        is_welded     = pre["is_welded"],

        # ── Géométrie ────────────────────────────────────────────────────
        h  = pre["h"],
        b  = pre["b"],
        tw = pre["tw"],
        tf = pre["tf"],
        t  = pre["t"],
        A  = pre["A"],

        # ── Matériau ─────────────────────────────────────────────────────
        material_designation = material.designation,
        fy = material.fy,
        fu = material.fu,
        E  = material.E,
        G  = material.G,
        steel_type = material.steel_type,
        gamma_M0 = pre["gM0"],
        gamma_M1 = pre["gM1"],
        gamma_M2 = pre["gM2"],
        epsilon  = pre["epsilon"],

        # ── Résistances calculées ───────────────────────────────────────────
        Nt_Rd    = pre["nt_rd"],
        Nc_Rd    = pre["nc_rd"],
        My_c_Rd  = pre["my_c"],
        Mz_c_Rd  = pre["mz_c"],
        Vy_pl_Rd = pre["vy_pl"],
        Vz_pl_Rd = pre["vz_pl"],
        Mb_Rd    = pre["Mb_Rd"],
        Nb_y_Rd  = pre["Nb_Rd_y"],
        Nb_z_Rd  = pre["Nb_Rd_z"],
        Nb_TF_Rd = pre["Nb_Rd_TF"],

        # ── Paramètres de stabilité ──────────────────────────────────────
        lambda_y   = pre["lambda_bar_y"],
        lambda_z   = pre["lambda_bar_z"],
        lambda_LT  = pre["lambda_bar_LT"],
        lambda_LT0 = pre["lambda_LT0"],
        Mcr        = pre["Mcr"],

        # ── Efforts internes maximaux (MAX des valeurs absolues) ──────────
        NEd_t_max = _max_abs(rows, "NEd_t"),
        NEd_c_max = _max_abs(rows, "NEd_c"),
        Vy_max    = _max_abs(rows, "Vy_Ed"),
        Vz_max    = _max_abs(rows, "Vz_Ed"),
        T_max     = _max_abs(rows, "TEd"),
        My_max    = _max_abs(rows, "My_Ed"),
        Mz_max    = _max_abs(rows, "Mz_Ed"),

        # ── Ratios maximaux ────────────────────────────────────────────────
        max_ratios = max_ratios,
        overall_max_ratio = overall_max,
        shear_buckling_warning = not shear_ok,
    )


def build_format1(
    rc_configs: list[RCConfig],
    materials: dict[int, MaterialConfig],
    format2: list[ElementLCResult],
) -> list[RCSummary]:
    """
    Construit le Format 1 complet : une RCSummary par RC, dans l'ordre de
    `rc_configs`.

    Paramètres
    ----------
    rc_configs : liste des configurations RC
    materials  : dict {material_number → MaterialConfig}
    format2    : résultats détaillés (Format 2), toutes RC confondus
                 — typiquement la sortie de dispatch.run_all()

    Retour
    ------
    list[RCSummary]
    """
    summaries: list[RCSummary] = []
    for rc in rc_configs:
        mat  = materials[rc.material_number]
        rows = [r for r in format2 if r.rc_number == rc.rc_number]
        summaries.append(build_rc_summary(rc, mat, rows))
    return summaries


# ─── Avertissements non bloquants ────────────────────────────────────────────

def build_warnings(format1: list[RCSummary]) -> list[str]:
    """
    Construit la liste des avertissements non bloquants pour la réponse API.

    Avertissements générés
    -----------------------
    - Section de classe 4 : résistances de section hors méthode EC3 simplifiée
      de l'outil (Nt,Rd, Nc,Rd, Mc,Rd, Nb,Rd, Mb,Rd = None pour ce RC).
    - Voilement par cisaillement non négligeable (h/tw > limite §6.2.6(6)) :
      vérification complémentaire requise hors de cet outil.
    """
    warnings: list[str] = []
    for s in format1:
        if s.section_class == "4":
            warnings.append(
                f"RC {s.rc_number} ({s.designation}) : section de classe 4 — "
                f"résistances de section et de stabilité non vérifiées par "
                f"cet outil (méthode EC3 limitée aux classes 1-3)."
            )
        if s.shear_buckling_warning:
            warnings.append(
                f"RC {s.rc_number} ({s.designation}) : voilement par "
                f"cisaillement de l'âme non négligeable (h/tw élevé) — "
                f"vérification complémentaire requise selon EN 1993-1-5."
            )
    return warnings


# ─── Assemblage final ─────────────────────────────────────────────────────────

def build_response(
    rc_configs: list[RCConfig],
    materials: dict[int, MaterialConfig],
    all_lc: pd.DataFrame,
    extra_warnings: list[str] | None = None,
) -> CalculationResponse:
    """
    Construit la réponse complète de POST /api/calculate.

    Paramètres
    ----------
    rc_configs     : liste des configurations RC (CalculationRequest.rc_configs)
    materials      : dict {material_number → MaterialConfig}
    all_lc         : DataFrame complet des efforts internes, déjà filtré des
                     éléments orphelins / RC non configurés (voir main.py)
                     [element_id, rc_number, lc_name, NEd_t, NEd_c, Fy, Fz, Mx, My, Mz]
                     — issu de parsers.split_axial(build_all_lc(...))
    extra_warnings : avertissements déjà générés en amont (main.py, étapes 5-6 :
                     éléments/RC écartés du calcul) — préfixés aux warnings
                     générés ici (classe 4, voilement par cisaillement)

    Retour
    ------
    CalculationResponse :
        format1, format2, nb_elements, nb_load_cases, nb_combinations, warnings
    """
    format2 = run_all(rc_configs, materials, all_lc)
    format1 = build_format1(rc_configs, materials, format2)
    warnings = list(extra_warnings or []) + build_warnings(format1)

    nb_elements   = len({r.element_id for r in format2})
    nb_load_cases = len({r.lc_name for r in format2})

    return CalculationResponse(
        format1=format1,
        format2=format2,
        nb_elements=nb_elements,
        nb_load_cases=nb_load_cases,
        nb_combinations=len(format2),
        warnings=warnings,
    )
    
