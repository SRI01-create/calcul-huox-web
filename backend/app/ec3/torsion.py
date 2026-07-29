"""
Phase 8 — Contrainte de torsion et cisaillement réduit par torsion.

Formules extraites directement des colonnes BB, BC, BD
des feuilles H / U / O / X (ligne 61 du fichier Excel).

Fonctions publiques
-------------------
    tau_w_H(TEd, Sw, IW, tf_mm)                             → float
    tau_mixed_U(TEd, Sw_w, IW, tw_mm, tf_mm, It, is_angle)  → float | None
    tau_bredt_O(TEd, h_mm, b_mm, t_mm, is_circular)          → float
    tau_solid_X(TEd, h_mm, b_mm, is_circular)                → float
    Vpl_T_Rd_H  (Vpl_Rd, tau, fy, gM0)                      → float | None
    Vpl_T_Rd_UOX(Vpl_Rd, tau, fy, gM0)                      → float | None

Unités
------
    TEd, Sw, Sw_w, IW, It  : SI (N.m, m⁴, m⁴, m⁶, m⁴)
    h_mm, b_mm, t_mm,
    tw_mm, tf_mm            : mm
    Vpl_Rd                  : N
    fy                      : MPa
    gM0                     : —
    τ retourné              : MPa
    Vpl,T,Rd retourné       : N
    None                    : vérification non applicable ("X" dans Excel)

Résumé des formules Excel
--------------------------
BB (H)   : ABS((TEd*Sw/IW/(tf/1000))/1e6)
BB (U canal) : MAX(|TEd*Sw_w/IW/min_t_m|, |TEd*max_t_m/It|) / 1e6
BB (U cornière) : IF(TEd=0, 0, "X")
BB (O Tci)  : ABS(TEd/(2*(t/1000)*2π*((h-t)/2/1000)²)/1e6)
BB (O rect) : ABS(TEd/(2*(t/1000)*(h-t)_m*(b-t)_m)/1e6)
BB (X Pci)  : ABS(16*TEd/(π*(h/1000)³)/1e6)
BB (X rect) : ABS((3+1.8*min/max)*TEd/((max/1000)*(min/1000)²)/1e6)

BC/BD (H)   : IF(factor≤0,"X", Vpl*(factor)^0.5)  factor = 1-τ/(1.25*τRd)
BC/BD (U,O,X): IF(BB="X","X", IF(Vpl*(1-τ/τRd)≤0,"X", Vpl*(1-τ/τRd)))
avec τRd = fy/(√3*gM0)
"""

from __future__ import annotations
import math

_SQRT3 = math.sqrt(3.0)


# ══════════════════════════════════════════════════════════════════════════════
# CONTRAINTES DE TORSION (colonne BB)
# ══════════════════════════════════════════════════════════════════════════════

def tau_w_H(TEd: float, Sw: float, IW: float, tf_mm: float) -> float:
    """
    Torsion non uniforme (gauchissement) — section H/I [MPa].

    Formule Excel : ABS((H*AK/AJ/(Y/1000))/1e6)
      H=TEd (N.m),  AK=Sw (m⁴),  AJ=IW (m⁶),  Y=tf (mm)

    τw,Ed = |TEd · Sw / IW / (tf/1000)| / 1e6
    """
    return abs(TEd * Sw / IW / (tf_mm / 1000.0)) / 1e6


def tau_mixed_U(
    TEd: float,
    Sw_w: float,
    IW: float,
    tw_mm: float,
    tf_mm: float,
    It: float,
    is_angle: bool = False,
) -> float | None:
    """
    Torsion mixte (gauchissement + St. Venant) — section U/canal [MPa].

    Formule Excel :
      Cornière : IF(TEd=0, 0, "X")       → None si TEd ≠ 0
      Canal    : MAX( |TEd·Sw_w/IW/min_t_m|,  |TEd·max_t_m/It| ) / 1e6
        min_t_m = MIN(tw, tf)/1000   (épaisseur minimale)
        max_t_m = MAX(tw, tf)/1000   (épaisseur maximale)

    Paramètres
    ----------
    Sw_w  : moment sectoriel d'âme (m⁴)  — col. AK feuille U
    IW    : constante de gauchissement (m⁶) — col. AJ
    It    : constante de torsion St. Venant (m⁴) — col. AI
    """
    if is_angle:
        return 0.0 if TEd == 0.0 else None   # "X" si torsion non nulle

    min_t_m = min(tw_mm, tf_mm) / 1000.0
    max_t_m = max(tw_mm, tf_mm) / 1000.0
    tau_gauchissement = abs(TEd * Sw_w / IW / min_t_m) / 1e6
    tau_sv            = abs(TEd * max_t_m / It) / 1e6
    return max(tau_gauchissement, tau_sv)


def tau_bredt_O(
    TEd: float,
    h_mm: float,
    b_mm: float | None,
    t_mm: float,
    is_circular: bool,
) -> float:
    """
    Torsion de Bredt — section creuse O [MPa].

    Formule Excel : ABS(H/(2*(X/1000)*Am)/1e6)
      Tci : Am = 2*PI()*(((V-X)/2)/1000)²
      Rect: Am = (V-X)/1000 * (W-X)/1000

    τ = |TEd / (2 · t_m · Am)| / 1e6

    Note : pour Tci, l'Excel utilise Am = 2π·rm²
    (rm = (D-t)/2 en m). Formule reproduite à l'identique.
    """
    t_m = t_mm / 1000.0

    if is_circular:
        rm_m = (h_mm - t_mm) / 2.0 / 1000.0
        Am   = 2.0 * math.pi * rm_m ** 2        # formule exacte Excel
    else:
        b_eff = h_mm if b_mm is None else b_mm
        Am    = (h_mm - t_mm) / 1000.0 * (b_eff - t_mm) / 1000.0

    return abs(TEd / (2.0 * t_m * Am)) / 1e6


def tau_solid_X(
    TEd: float,
    h_mm: float,
    b_mm: float | None,
    is_circular: bool,
) -> float:
    """
    Torsion de Timoshenko — section pleine X [MPa].

    Formule Excel :
      Pci    : ABS(16*H/(PI()*(V/1000)³)/1e6)
      Pca/Pre: ABS((3+1.8*min/max)*H/((max/1000)*(min/1000)²)/1e6)
               max = MAX(h,b),  min = MIN(h,b)
    """
    if is_circular:
        d_m = h_mm / 1000.0
        return abs(16.0 * TEd / (math.pi * d_m ** 3)) / 1e6
    else:
        b_eff = h_mm if b_mm is None else b_mm
        a_m   = max(h_mm, b_eff) / 1000.0    # grande dimension
        b_m   = min(h_mm, b_eff) / 1000.0    # petite dimension
        return abs((3.0 + 1.8 * b_m / a_m) * TEd / (a_m * b_m ** 2)) / 1e6


# ══════════════════════════════════════════════════════════════════════════════
# CISAILLEMENT RÉDUIT PAR TORSION (colonnes BC et BD)
# Mêmes fonctions pour Vy,pl,T,Rd et Vz,pl,T,Rd :
# passer Vy_pl_Rd pour BC, Vz_pl_Rd pour BD.
# ══════════════════════════════════════════════════════════════════════════════

def Vpl_T_Rd_H(
    Vpl_Rd: float,
    tau: float,
    fy: float,
    gM0: float,
) -> float | None:
    """
    Cisaillement réduit par torsion — section H [N].

    Formule Excel : IF((1-BB/(1.25*(fy/√3/gM0)))≤0, "X",
                       Vpl*(1-BB/(1.25*(fy/√3/gM0)))^0.5)

    Vpl,T,Rd = Vpl,Rd · (1 - τw / (1.25·τRd))^0.5    [§6.2.7(9)]
    τRd = fy / (√3 · γM0)

    Facteur 1.25 et réduction par RACINE CARRÉE spécifiques aux sections H.
    Retourne None si τ ≥ 1.25·τRd (torsion épuise la capacité).
    """
    tau_rd  = fy / _SQRT3 / gM0
    factor  = 1.0 - tau / (1.25 * tau_rd)
    if factor <= 0.0:
        return None
    return Vpl_Rd * math.sqrt(factor)


def Vpl_T_Rd_UOX(
    Vpl_Rd: float,
    tau: float | None,
    fy: float,
    gM0: float,
) -> float | None:
    """
    Cisaillement réduit par torsion — sections U, O et X [N].

    Formule Excel : IF(BB="X","X",
                       IF(Vpl*(1-BB/τRd)≤0,"X",
                          Vpl*(1-BB/τRd)))

    Vpl,T,Rd = Vpl,Rd · (1 - τ / τRd)    [linéaire, sans facteur 1.25]
    τRd = fy / (√3 · γM0)

    Retourne None si :
      - tau est None (propagation du "X" — cornière avec torsion)
      - Vpl*(1-τ/τRd) ≤ 0 (torsion épuise la capacité)
    """
    if tau is None:
        return None
    tau_rd = fy / _SQRT3 / gM0
    result = Vpl_Rd * (1.0 - tau / tau_rd)
    if result <= 0.0:
        return None
    return result
