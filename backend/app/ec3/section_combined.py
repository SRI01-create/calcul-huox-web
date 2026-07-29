"""
Phase 9 — Résistances de section combinées (flexion réduite par cisaillement
et par effort normal) + ratio combiné N+V+M.

Formules extraites des colonnes BE, BF, BG, BH, BR
des feuilles H / U / O / X (ligne 61 du fichier Excel).

Fonctions publiques
-------------------
    MV_Rd(Mc_Rd, Vy_Ed, Vy_pl_T_Rd, Vz_Ed, Vz_pl_T_Rd, section_class)
        → float | None  — flexion réduite par cisaillement (BE, BF)

    My_N_Rd_HU(My_V_Rd, n_N, A, b_mm, tf_mm)   → float | None  (BG — H et U)
    Mz_N_Rd_HU(Mz_V_Rd, n_N, A, b_mm, tf_mm)   → float | None  (BH — H et U)
    My_N_Rd_O (My_V_Rd, n_N, A, b_mm, t_mm)    → float | None  (BG — O)
    Mz_N_Rd_O (Mz_V_Rd, n_N, A, h_mm, t_mm)    → float | None  (BH — O)
    MN_Rd_X   (MV_Rd,   n_N)                    → float | None  (BG/BH — X)

    ratio_combined_H  (section_class, My_Ed, Mz_Ed,
                       My_N_Rd, Mz_N_Rd, My_V_Rd, Mz_V_Rd, n_N) → float | None
    ratio_combined_U  (...)   → float | None  (BR — U)
    ratio_combined_O  (..., is_circular) → float | None  (BR — O)
    ratio_combined_X  (My_Ed, Mz_Ed, My_N_Rd, Mz_N_Rd,
                       My_V_Rd, Mz_V_Rd, n_N) → float | None  (BR — X)

Paramètre n_N
-------------
    n_N = MAX(NEd_t/Nt_Rd ; NEd_c/Nc_Rd) — calculé par l'engine avant l'appel.

Retour None
-----------
    Section classe 4, entrée None propagée, résultat ≤ 0 ou division nulle.

Unités
------
    Mc_Rd, MV_Rd, MN_Rd  : N.m
    V_Ed, Vpl             : N
    A                     : m²
    b_mm, tf_mm, t_mm,
    h_mm                  : mm
    n_N                   : sans dimension ∈ [0, 1] théoriquement
"""

from __future__ import annotations
import math


# ══════════════════════════════════════════════════════════════════════════════
# FLEXION RÉDUITE PAR CISAILLEMENT — colonnes BE et BF (identiques H, U, O, X)
# ══════════════════════════════════════════════════════════════════════════════

def MV_Rd(
    Mc_Rd:       float | None,
    Vy_Ed:       float,
    Vy_pl_T_Rd:  float | None,
    Vz_Ed:       float,
    Vz_pl_T_Rd:  float | None,
    section_class: int,
) -> float | None:
    """
    Flexion réduite par cisaillement (N.m) — valable pour My et Mz.
    Passer Mc_Rd = My,c,Rd pour obtenir My,V,Rd ;
    passer Mc_Rd = Mz,c,Rd pour obtenir Mz,V,Rd.

    Formule Excel : col. BE (et BF) — identique dans H, U, O, X
    ------------------------------------------------------------
    ρ = 0                         si n_V ≤ 0.5
        (2·n_V − 1)²              sinon
    avec n_V = MAX(|Vy|/Vy,pl,T,Rd ; |Vz|/Vz,pl,T,Rd)

    M_V,Rd = Mc,Rd · (1 − ρ)

    Retourne None si :
      - classe 4 (check "U=4" dans Excel)
      - Vy,pl,T,Rd ou Vz,pl,T,Rd est None (BC="X" ou BD="X")
      - Mc_Rd est None
      - résultat ≤ 0
    """
    if section_class == 4 or Mc_Rd is None:
        return None
    if Vy_pl_T_Rd is None or Vz_pl_T_Rd is None:
        return None

    n_V = max(
        abs(Vy_Ed) / Vy_pl_T_Rd if Vy_pl_T_Rd > 0 else 0.0,
        abs(Vz_Ed) / Vz_pl_T_Rd if Vz_pl_T_Rd > 0 else 0.0,
    )
    rho = 0.0 if n_V <= 0.5 else (2.0 * n_V - 1.0) ** 2
    result = Mc_Rd * (1.0 - rho)
    return result if result > 0.0 else None


# ══════════════════════════════════════════════════════════════════════════════
# FLEXION RÉDUITE PAR EFFORT NORMAL — colonnes BG et BH
# ══════════════════════════════════════════════════════════════════════════════

def _a_param(A: float, dim1_mm: float, dim2_mm: float) -> float:
    """
    Paramètre a = MIN(0.5, (A − 2·d1_m·d2_m) / A).
    d1, d2 : deux dimensions en mm (ex. b et tf pour H/U ; b et t pour O BG).
    """
    aw = (A - 2.0 * (dim1_mm / 1000.0) * (dim2_mm / 1000.0)) / A
    return min(0.5, aw)


# ─── H et U ─────────────────────────────────────────────────────────────────

def My_N_Rd_HU(
    My_V_Rd: float | None,
    n_N: float,
    A: float,
    b_mm: float,
    tf_mm: float,
) -> float | None:
    """
    My,N,Rd pour sections H et U [N.m].

    Formule Excel : col. BG feuilles H et U
    ----------------------------------------
    a = MIN(0.5, (A − 2·b_m·tf_m) / A)
    My,N,Rd = MIN(My,V,Rd ; My,V,Rd · (1 − n_N) / (1 − 0.5·a))

    La formule MIN assure implicitement : si n_N ≤ a → pas de réduction.
    Retourne None si My,V,Rd est None ou si résultat ≤ 0.
    """
    if My_V_Rd is None:
        return None
    a = _a_param(A, b_mm, tf_mm)
    denom = 1.0 - 0.5 * a
    if denom <= 0.0:
        return None
    result = min(My_V_Rd, My_V_Rd * (1.0 - n_N) / denom)
    return result if result > 0.0 else None


def Mz_N_Rd_HU(
    Mz_V_Rd: float | None,
    n_N: float,
    A: float,
    b_mm: float,
    tf_mm: float,
) -> float | None:
    """
    Mz,N,Rd pour sections H et U [N.m].

    Formule Excel : col. BH feuilles H et U  — DIFFÉRENTE de BG !
    ---------------------------------------------------------------
    a = MIN(0.5, (A − 2·b_m·tf_m) / A)
    si n_N ≤ a  →  Mz,N,Rd = Mz,V,Rd  (pas de réduction)
    sinon       →  Mz,N,Rd = Mz,V,Rd · (1 − ((n_N − a)/(1 − a))²)

    EC3 §6.2.9.1 : formules distinctes pour My et Mz sur sections I/H.
    """
    if Mz_V_Rd is None:
        return None
    a = _a_param(A, b_mm, tf_mm)
    if n_N <= a:
        return Mz_V_Rd
    denom = 1.0 - a
    if denom <= 0.0:
        return None
    result = Mz_V_Rd * (1.0 - ((n_N - a) / denom) ** 2)
    return result if result > 0.0 else None


# ─── O ──────────────────────────────────────────────────────────────────────

def My_N_Rd_O(
    My_V_Rd: float | None,
    n_N: float,
    A: float,
    b_mm: float | None,
    t_mm: float,
) -> float | None:
    """
    My,N,Rd pour sections creuses O [N.m].

    Formule Excel : col. BG feuille O
    ----------------------------------
    a_y = MIN(0.5, (A − 2·b_m·t_m) / A)   [faces perpendiculaires à y]
    My,N,Rd = MIN(My,V,Rd ; My,V,Rd · (1−n_N) / (1−0.5·a_y))

    b_mm = None pour Tci → b_m = 0 → a_y = MIN(0.5, 1.0) = 0.5
    """
    if My_V_Rd is None:
        return None
    b_eff = 0.0 if b_mm is None else b_mm
    a = _a_param(A, b_eff, t_mm)
    denom = 1.0 - 0.5 * a
    if denom <= 0.0:
        return None
    result = min(My_V_Rd, My_V_Rd * (1.0 - n_N) / denom)
    return result if result > 0.0 else None


def Mz_N_Rd_O(
    Mz_V_Rd: float | None,
    n_N: float,
    A: float,
    h_mm: float,
    t_mm: float,
) -> float | None:
    """
    Mz,N,Rd pour sections creuses O [N.m].

    Formule Excel : col. BH feuille O
    ----------------------------------
    a_z = MIN(0.5, (A − 2·h_m·t_m) / A)   [faces perpendiculaires à z]
    Mz,N,Rd = MIN(Mz,V,Rd ; Mz,V,Rd · (1−n_N) / (1−0.5·a_z))

    Même structure que My_N_Rd_O, axe différent.
    """
    if Mz_V_Rd is None:
        return None
    a = _a_param(A, h_mm, t_mm)
    denom = 1.0 - 0.5 * a
    if denom <= 0.0:
        return None
    result = min(Mz_V_Rd, Mz_V_Rd * (1.0 - n_N) / denom)
    return result if result > 0.0 else None


# ─── X ──────────────────────────────────────────────────────────────────────

def MN_Rd_X(MV_Rd: float | None, n_N: float) -> float | None:
    """
    M,N,Rd pour sections pleines X [N.m] — My et Mz utilisent la même formule.

    Formule Excel : col. BG et BH feuille X
    -----------------------------------------
    M,N,Rd = M,V,Rd · (1 − n_N²)

    Retourne None si (1 − n_N) ≤ 0 (contrôle de l'Excel : `IF((1-n_N)<=0,"X",...)`).
    """
    if MV_Rd is None:
        return None
    if (1.0 - n_N) <= 0.0:
        return None
    result = MV_Rd * (1.0 - n_N ** 2)
    return result if result > 0.0 else None


# ══════════════════════════════════════════════════════════════════════════════
# RATIO COMBINÉ N+V+M — colonne BR
# ══════════════════════════════════════════════════════════════════════════════

def _safe_val(num: float, denom: float | None) -> float | None:
    """num/denom avec protection None et division nulle."""
    if denom is None or denom == 0.0:
        return None
    return num / denom


def _max_notnone(*vals) -> float | None:
    """MAX des valeurs non-None ; None si toutes None."""
    clean = [v for v in vals if v is not None]
    return max(clean) if clean else None


def ratio_combined_H(
    section_class: int,
    My_Ed: float,
    Mz_Ed: float,
    My_N_Rd: float | None,
    Mz_N_Rd: float | None,
    My_V_Rd: float | None,
    Mz_V_Rd: float | None,
    n_N: float,
) -> float | None:
    """
    Ratio combiné section N+V+M — section H (col. BR feuille H).

    Classe 1/2 : (My/My,N,Rd)² + (|Mz/Mz,N,Rd|)^MAX(1; 5·n_N)
    Classe 3   : n_N + |My/My,V,Rd| + |Mz/Mz,V,Rd|

    Résultat = MAX(terme_combiné ; My/My,N,Rd ; Mz/Mz,N,Rd)
    ISERROR de l'Excel → None si toutes les entrées sont None.
    """
    if section_class == 4:
        return None

    r_My_N = _safe_val(My_Ed, My_N_Rd)
    r_Mz_N = _safe_val(Mz_Ed, Mz_N_Rd)

    if section_class in (1, 2):
        if My_N_Rd is None or Mz_N_Rd is None:
            comb = None
        else:
            beta  = max(1.0, 5.0 * n_N)
            comb  = (My_Ed / My_N_Rd) ** 2 + abs(Mz_Ed / Mz_N_Rd) ** beta
    else:  # class 3
        if My_V_Rd is None or Mz_V_Rd is None:
            comb = None
        else:
            comb = n_N + abs(My_Ed / My_V_Rd) + abs(Mz_Ed / Mz_V_Rd)

    return _max_notnone(comb, r_My_N, r_Mz_N)


def ratio_combined_U(
    section_class: int,
    My_Ed: float,
    Mz_Ed: float,
    My_N_Rd: float | None,
    Mz_N_Rd: float | None,
    My_V_Rd: float | None,
    Mz_V_Rd: float | None,
    n_N: float,
) -> float | None:
    """
    Ratio combiné section N+V+M — section U (col. BR feuille U).

    Classe 1/2 : |My/My,N,Rd| + |Mz/Mz,N,Rd|          [linéaire — différent de H !]
    Classe 3   : n_N + |My/My,V,Rd| + |Mz/Mz,V,Rd|     [idem H]

    Résultat = MAX(terme_combiné ; My/My,N,Rd ; Mz/Mz,N,Rd)
    """
    if section_class == 4:
        return None

    r_My_N = _safe_val(My_Ed, My_N_Rd)
    r_Mz_N = _safe_val(Mz_Ed, Mz_N_Rd)

    if section_class in (1, 2):
        if My_N_Rd is None or Mz_N_Rd is None:
            comb = None
        else:
            comb = abs(My_Ed / My_N_Rd) + abs(Mz_Ed / Mz_N_Rd)
    else:
        if My_V_Rd is None or Mz_V_Rd is None:
            comb = None
        else:
            comb = n_N + abs(My_Ed / My_V_Rd) + abs(Mz_Ed / Mz_V_Rd)

    return _max_notnone(comb, r_My_N, r_Mz_N)


def ratio_combined_O(
    section_class: int,
    My_Ed: float,
    Mz_Ed: float,
    My_N_Rd: float | None,
    Mz_N_Rd: float | None,
    My_V_Rd: float | None,
    Mz_V_Rd: float | None,
    n_N: float,
    is_circular: bool,
) -> float | None:
    """
    Ratio combiné section N+V+M — section O (col. BR feuille O).

    Classe 1/2 — Tci  : (|My/My,N|)² + (|Mz/Mz,N|)²
    Classe 1/2 — rect : (|My/My,N|)^α + (|Mz/Mz,N|)^α
                         α = MIN(6 ; 1.66/(1 − 1.13·n_N²))
    Classe 3           : n_N + |My/My,V| + |Mz/Mz,V|

    Résultat = MAX(terme_combiné ; My/My,N,Rd ; Mz/Mz,N,Rd)
    """
    if section_class == 4:
        return None

    r_My_N = _safe_val(My_Ed, My_N_Rd)
    r_Mz_N = _safe_val(Mz_Ed, Mz_N_Rd)

    if section_class in (1, 2):
        if My_N_Rd is None or Mz_N_Rd is None:
            comb = None
        else:
            if is_circular:
                alpha = 2.0
            else:
                denom_a = 1.0 - 1.13 * n_N ** 2
                alpha = min(6.0, 1.66 / denom_a) if denom_a > 0 else 6.0
            comb = abs(My_Ed / My_N_Rd) ** alpha + abs(Mz_Ed / Mz_N_Rd) ** alpha
    else:
        if My_V_Rd is None or Mz_V_Rd is None:
            comb = None
        else:
            comb = n_N + abs(My_Ed / My_V_Rd) + abs(Mz_Ed / Mz_V_Rd)

    return _max_notnone(comb, r_My_N, r_Mz_N)


def ratio_combined_X(
    My_Ed: float,
    Mz_Ed: float,
    My_N_Rd: float | None,
    Mz_N_Rd: float | None,
    My_V_Rd: float | None,
    Mz_V_Rd: float | None,
    n_N: float,
) -> float | None:
    """
    Ratio combiné section N+V+M — section X (col. BR feuille X).

    Formule Excel : IF(OR(BG="X",BH="X",BE="X",BF="X"), "X",
                       MAX(n_N+|My/My,V|+|Mz/Mz,V|,  My/My,N+Mz/Mz,N))

    Toujours linéaire (X = toujours classe 1).
    Note : le second terme My/My,N + Mz/Mz,N est signé (sans ABS) dans Excel.
    """
    if any(v is None for v in (My_N_Rd, Mz_N_Rd, My_V_Rd, Mz_V_Rd)):
        return None

    t1 = n_N + abs(My_Ed / My_V_Rd) + abs(Mz_Ed / Mz_V_Rd)   # type: ignore[operator]
    t2 = My_Ed / My_N_Rd + Mz_Ed / Mz_N_Rd                     # type: ignore[operator]
    return max(t1, t2)
