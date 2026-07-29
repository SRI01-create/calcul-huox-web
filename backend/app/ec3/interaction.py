"""
Phase 14 — Facteurs d'interaction kyy/kyz/kzy/kzz et ratios combinés (§6.3.3).

Implémente la méthode Annexe B de NF EN 1993-1-1 pour les sections de classe 1-3
et la méthode simplifiée de NF EN 1993-1-4 §5.2.3 pour les sections inox.

Colonnes Excel de référence (formules identiques H/U/O/X sauf gardes)
─────────────────────────────────────────────────────────────────────
    DC   n_Ed          ratio compression réduit = NEd_c / (A·fy/γM0)
    DD   C_IT          MAX(1 − It/Iy, 0)
    DM   wy            MIN(Wpl_y/Wel_y, 1.5)
    DN   wz            MIN(Wpl_z/Wel_z, 1.5)
    DO   ε_y           (1−n_Ed·Ncr_min/Ncr_min) / (1−χ_y·NEd_c/Ncr_min)
    DP   ε_z           idem avec χ_z
    DE   aux_yy        0.5·C_IT·δ²·My·Mz / (χ_LT·W_ref·Mel_y·Mel_z)
    DF   aux_yz        10·C_IT·δ²·My / (5 + λ̄⁴·Cmy·χ_LT·W_ref·Mel_y)
    DG   aux_zy        2·C_IT·δ·My·Mz / (0.1 + λ̄⁴·Cmy·Cmz·χ_LT·W_ref·Mel_y·Mel_z)
    DH   aux_zz        1.7·C_IT·δ·My / (0.1 + λ̄⁴·Cmy·χ_LT·W_ref·Mel_y)
    DI   C_yy          MAX(1+(wy−1)·((...·DC−DE),  1/wy)
    DJ   C_yz          MAX(1+(wz−1)·(...·DC−DF),  0.6·(wz/wy)^0.5/wy)
    DK   C_zy          MAX(1+(wy−1)·(...·DC−DG),  0.6·(wy/wz)^0.5/wy)
    DL   C_zz          MAX(1+(wz−1)·(...·DC−DH),  1/wy)  [borne =AD/AE]
    CY   kyy (carbone) Cmy·CmLT·DO/(1−NEd/Ncr_min)/C_yy   (cl.1/2)
    CZ   kyz (carbone) Cmz·DO/(1−NEd/Ncr_min)·(1/C_yz)·0.6·(wz/wy)^0.5  (cl.1/2)
    DA   kzy (carbone) Cmy·CmLT·DP/(1−NEd/Ncr_min)·(1/C_zy)·0.6·(wy/wz)^0.5 (cl.1/2)
    DB   kzz (carbone) Cmz·DP/(1−NEd/Ncr_min)/C_zz   (cl.1/2)
    DU   kyy (inox)    MIN(MAX(1.2, 1+2·(λ̄_max−0.5)·NEd/Nb_y), 1.2+2·NEd/Nb_y)
    DV   kyz/kzy/kzz (inox) idem avec Nb_z
    DW   1.0           constante (cellule $DW$56)
    CW   ratio eq.1    ROUNDUP(NEd/Nb_Rd_min_y + |kyy·My/M_Rd_y| + |kyz·Mz/Mz_c_Rd|, 2)
    CX   ratio eq.2    ROUNDUP(NEd/Nb_Rd_z     + |kzy·My/M_Rd_y| + |kzz·Mz/Mz_c_Rd|, 2)

Notes importantes
─────────────────
  χ_LT dans DE-DH : recalculé avec λ_LT0 = 0.2 (hardcodé), alpha H-type (b/h),
                    MIN(1, χ) sans borne 1/λ̄² — identique sur les 4 feuilles.
  Mz terme CW/CX  : toujours Mz,c,Rd (phase 7), pas de déversement sur z.
  My terme CW     : Mb,Rd si LTB (H+carbon, U+carbon), My,c,Rd sinon (O, X, inox).
  My terme CX     : Mb,Rd pour H+carbon et H+inox (DW=1 × My/Mb,Rd); My,c,Rd pour O/X.
  U section CW/CX : Nb,Rd,min = MIN(Nb,Rd,y, Nb,Rd,z, Nb,Rd,TF) (Phase 11).
  O/X sections    : IF(NEd_c=0, 0, ROUNDUP(...)) — retournent 0 si pas de compression.
  Classe 4        : retourne "X" (None) dans Excel → None en Python.

Références normatives
─────────────────────
  NF EN 1993-1-1 §6.3.3, Annexe B §B.2
  NF EN 1993-1-4 §5.2.3
"""

from __future__ import annotations

import math
from typing import Optional

from .utils import buckling_curve_alpha, chi_reduction


# ─── χ_LT interne pour DE-DH ─────────────────────────────────────────────────

def _chi_LT_for_k(
    lambda_bar_LT: float,
    fabrication: str,
    b: float,
    h: float,
) -> float:
    """
    χ_LT pour les termes auxiliaires DE, DF, DG, DH.

    Différences vs Phase 13 :
    - λ_LT0 = 0.2  (hardcodé dans les formules DE..DH)
    - α_LT_mod = formule H-type (même sur feuilles U/O/X)
    - Pas de borne 1/λ̄²
    - MIN(1, chi_raw)

    Extrait des formules DE..DH (identiques sur les 4 feuilles).
    """
    if lambda_bar_LT <= 0:
        return 1.0
    ratio = b / h
    lam2  = lambda_bar_LT ** 2
    if fabrication == "L":
        alpha = max(0.0, 0.4 - 0.2 * ratio * lam2)
    else:
        alpha = max(0.0, 0.5 - 0.25 * ratio * lam2)
    Phi     = 0.5 * (1.0 + alpha * (lambda_bar_LT - 0.2) + lam2)
    disc    = max(0.0, Phi ** 2 - lam2)
    chi_raw = 1.0 / (Phi + math.sqrt(disc))
    return min(1.0, chi_raw)


# ─── Facteurs auxiliaires (Annex B) ──────────────────────────────────────────

def _W_ref(classe: int, Wpl_y: float, Wel_y: float) -> Optional[float]:
    """W_ref utilisé dans DE-DH : Wel_y (cl.1/2) ou Wpl_y (cl.3)."""
    if classe <= 2:
        return Wel_y
    if classe == 3:
        return Wpl_y
    return None


def _aux_DE(
    C_IT: float, lam_LT: float, My: float, Mz: float,
    chi_LT: float, W_ref: float, Mel_y: float, Mel_z: float,
) -> float:
    """DE = 0.5·C_IT·0.04·My·Mz / (χ_LT·W_ref·Mel_y·Mel_z)"""
    denom = chi_LT * W_ref * Mel_y * Mel_z
    if denom == 0:
        return 0.0
    return 0.5 * C_IT * 0.04 * My * Mz / denom


def _aux_DF(
    C_IT: float, lam_max: float, Cmy: float, My: float,
    chi_LT: float, W_ref: float, Mel_y: float,
) -> float:
    """DF = 10·C_IT·0.04·My / (5 + λ̄⁴·Cmy·χ_LT·W_ref·Mel_y)"""
    denom = 5.0 + lam_max ** 4 * Cmy * chi_LT * W_ref * Mel_y
    if denom == 0:
        return 0.0
    return 10.0 * C_IT * 0.04 * abs(My) / denom


def _aux_DG(
    C_IT: float, lam_max: float, Cmy: float, Cmz: float,
    My: float, Mz: float,
    chi_LT: float, W_ref: float, Mel_y: float, Mel_z: float,
) -> float:
    """DG = 2·C_IT·0.2·|My·Mz| / (0.1 + λ̄⁴·Cmy·Cmz·χ_LT·W_ref·Mel_y·Mel_z)"""
    denom = 0.1 + lam_max ** 4 * Cmy * Cmz * chi_LT * W_ref * Mel_y * Mel_z
    if denom == 0:
        return 0.0
    return 2.0 * C_IT * 0.2 * abs(My) * abs(Mz) / denom


def _aux_DH(
    C_IT: float, lam_max: float, Cmy: float, My: float,
    chi_LT: float, W_ref: float, Mel_y: float,
) -> float:
    """DH = 1.7·C_IT·0.2·|My| / (0.1 + λ̄⁴·Cmy·χ_LT·W_ref·Mel_y)"""
    denom = 0.1 + lam_max ** 4 * Cmy * chi_LT * W_ref * Mel_y
    if denom == 0:
        return 0.0
    return 1.7 * C_IT * 0.2 * abs(My) / denom


# ─── Facteurs C_yy..C_zz (DI-DL) ────────────────────────────────────────────

def _C_yy(wy: float, Cmy: float, lam: float, nEd: float, DE: float, inv_wy: float) -> float:
    """DI = MAX(1+(wy−1)·((2−1.6·Cmy²·λ̄/wy−1.6·Cmy²·λ̄²/wy)·nEd − DE), 1/wy)"""
    bracket = (2.0 - 1.6*Cmy**2*lam/wy - 1.6*Cmy**2*lam**2/wy) * nEd - DE
    return max(1.0 + (wy - 1.0) * bracket, inv_wy)


def _C_yz(wz: float, wy: float, Cmz: float, lam: float, nEd: float, DF: float, inv_wy: float) -> float:
    """DJ = MAX(1+(wz−1)·((2−14·Cmz²·λ̄²/wz⁵)·nEd − DF), 0.6·(wz/wy)^0.5/wy)"""
    bracket = (2.0 - 14.0*Cmz**2*lam**2/wz**5) * nEd - DF
    lower   = 0.6 * (wz/wy) ** 0.5 * inv_wy
    return max(1.0 + (wz - 1.0) * bracket, lower)


def _C_zy(wy: float, wz: float, Cmy: float, lam: float, nEd: float, DG: float, inv_wy: float) -> float:
    """DK = MAX(1+(wy−1)·((2−14·Cmy²·λ̄²/wy⁵)·nEd − DG), 0.6·(wy/wz)^0.5/wy)"""
    bracket = (2.0 - 14.0*Cmy**2*lam**2/wy**5) * nEd - DG
    lower   = 0.6 * (wy/wz) ** 0.5 * inv_wy
    return max(1.0 + (wy - 1.0) * bracket, lower)


def _C_zz(wz: float, Cmz: float, lam: float, nEd: float, DH: float, inv_wy: float) -> float:
    """DL = MAX(1+(wz−1)·((2−1.6·Cmz²·λ̄/wz−1.6·Cmz²·λ̄²/wz)·nEd − DH), 1/wy)"""
    bracket = (2.0 - 1.6*Cmz**2*lam/wz - 1.6*Cmz**2*lam**2/wz) * nEd - DH
    return max(1.0 + (wz - 1.0) * bracket, inv_wy)


# ─── Fonction principale ──────────────────────────────────────────────────────

def interaction_factors(
    # Section
    A: float,
    Iy: float,
    It: float,
    Wpl_y: float,
    Wel_y: float,
    Wpl_z: float,
    Wel_z: float,
    b: float,
    h: float,
    classe: int,
    # Matériau
    fy: float,
    gamma_M0: float,
    gamma_M1: float,
    is_stainless: bool,
    # Phase 10
    Ncr_min: float,
    Nb_Rd_y: Optional[float],
    Nb_Rd_z: Optional[float],
    lambda_bar_max: float,
    # Phase 11 (U only, sinon None)
    Nb_Rd_TF: Optional[float],
    # Phase 13
    lambda_bar_LT: Optional[float],
    Mb_Rd: Optional[float],
    # Phase 7
    My_c_Rd: float,
    Mz_c_Rd: float,
    # RC
    Cmy: float,
    Cmz: float,
    CmLT: float,
    fabrication: str,
    # Forces
    NEd_c: float,
    My_Ed: float,
    Mz_Ed: float,
    # Type de section
    section_type: str,
) -> dict:
    """
    Facteurs d'interaction kyy/kyz/kzy/kzz et vérifications combinées §6.3.3.

    Paramètres
    ----------
    A, Iy, It          : propriétés section (m², m⁴)
    Wpl_y, Wel_y       : modules plastique/élastique axe y (m³)
    Wpl_z, Wel_z       : modules plastique/élastique axe z (m³)
    b, h               : largeur/hauteur section (mm)
    classe             : classe de section (1–4)
    fy                 : limite élasticité (MPa)
    gamma_M0, gamma_M1 : coefficients partiels
    is_stainless       : True pour acier inox
    Ncr_min            : MIN(Ncr_y, Ncr_z) en N (Phase 10)
    Nb_Rd_y, Nb_Rd_z   : résistances flambement (N, Phase 10)
    lambda_bar_max     : MAX(λ̄_y, λ̄_z[, λ̄_T, λ̄_TF]) (Phase 10/11)
    Nb_Rd_TF           : résistance flambement torsion (N, Phase 11, None si != U)
    lambda_bar_LT      : élancement déversement (Phase 13, None si O/X)
    Mb_Rd              : moment résistance déversement (N·m, Phase 13, None si O/X)
    My_c_Rd, Mz_c_Rd   : résistances section en flexion (N·m, Phase 7)
    Cmy, Cmz, CmLT     : facteurs moment uniforme équivalent (user-input, défaut 1.0)
    fabrication        : "L" (laminé) | "S" (soudé)
    NEd_c              : effort compression (N ≥ 0)
    My_Ed, Mz_Ed       : moments fléchissants (N·m)
    section_type       : "H" | "U" | "O" | "X"

    Retour
    ------
    dict :
        DC, DD, DM, DN          : intermédiaires
        DO, DP                  : facteurs ε_y, ε_z
        DE, DF, DG, DH          : termes auxiliaires Annex B
        DI, DJ, DK, DL          : facteurs C_yy..C_zz
        kyy, kyz, kzy, kzz      : facteurs d'interaction (carbone)
        DU, DV, DW              : facteurs d'interaction (inox)
        ratio_CW                : ratio vérification eq.1 (§6.3.3 éq. 6.61)
        ratio_CX                : ratio vérification eq.2 (§6.3.3 éq. 6.62)

    Classe 4 → ratio_CW = ratio_CX = None.
    """
    fy_Pa    = fy * 1_000_000.0
    gM0      = gamma_M0
    gM1      = gamma_M1
    lam      = lambda_bar_max
    lam_LT   = lambda_bar_LT if lambda_bar_LT is not None else 0.0

    # ── Classe 4 → None ─────────────────────────────────────────────────────
    if classe == 4:
        return {k: None for k in (
            "DC","DD","DM","DN","DO","DP",
            "DE","DF","DG","DH","DI","DJ","DK","DL",
            "kyy","kyz","kzy","kzz",
            "DU","DV","DW","ratio_CW","ratio_CX",
        )}

    # ── DC — n_Ed ─────────────────────────────────────────────────────────
    A_fy_gM0 = A * fy_Pa / gM0
    DC = NEd_c / A_fy_gM0 if A_fy_gM0 > 0 else 0.0

    # ── DD — C_IT ─────────────────────────────────────────────────────────
    DD = max(1.0 - It / Iy, 0.0)

    # ── DM, DN ────────────────────────────────────────────────────────────
    DM = min(Wpl_y / Wel_y, 1.5) if Wel_y > 0 else 1.0
    DN = min(Wpl_z / Wel_z, 1.5) if Wel_z > 0 else 1.0
    inv_wy = Wel_y / Wpl_y   # = 1/DM, borne inférieure de DI et DL

    # ── DO, DP — facteurs ε (amplification) ─────────────────────────────
    # χ_y = Nb,Rd,y × γM1 / (A × fy),  idem χ_z
    if Nb_Rd_y is not None and Ncr_min > 0:
        chi_y = Nb_Rd_y * gM1 / (A * fy_Pa)
        denom_DO = 1.0 - chi_y * NEd_c / Ncr_min
        DO = (1.0 - NEd_c / Ncr_min) / denom_DO if abs(denom_DO) > 1e-12 else 1.0
    else:
        DO = 1.0

    if Nb_Rd_z is not None and Ncr_min > 0:
        chi_z = Nb_Rd_z * gM1 / (A * fy_Pa)
        denom_DP = 1.0 - chi_z * NEd_c / Ncr_min
        DP = (1.0 - NEd_c / Ncr_min) / denom_DP if abs(denom_DP) > 1e-12 else 1.0
    else:
        DP = 1.0

    # ── χ_LT pour DE-DH (λ_LT0=0.2 hardcodé, alpha H-type, pas de cap) ─
    chi_LT_k = _chi_LT_for_k(lam_LT, fabrication, b, h)

    # ── W_ref et moments élastiques pour DE-DH ───────────────────────────
    W_ref = _W_ref(classe, Wpl_y, Wel_y)
    if W_ref is None:
        W_ref = Wel_y    # fallback (classe 4 déjà traitée)
    Mel_y = Wel_y * fy_Pa / gM0
    Mel_z = Wel_z * fy_Pa / gM0

    # ── DE..DH ─────────────────────────────────────────────────────────
    DE = _aux_DE(DD, lam_LT, My_Ed, Mz_Ed, chi_LT_k, W_ref, Mel_y, Mel_z)
    DF = _aux_DF(DD, lam, Cmy, My_Ed, chi_LT_k, W_ref, Mel_y)
    DG = _aux_DG(DD, lam, Cmy, Cmz, My_Ed, Mz_Ed, chi_LT_k, W_ref, Mel_y, Mel_z)
    DH = _aux_DH(DD, lam, Cmy, My_Ed, chi_LT_k, W_ref, Mel_y)

    # ── DI..DL ────────────────────────────────────────────────────────
    DI = _C_yy(DM, Cmy, lam, DC, DE, inv_wy)
    DJ = _C_yz(DN, DM, Cmz, lam, DC, DF, inv_wy)
    DK = _C_zy(DM, DN, Cmy, lam, DC, DG, inv_wy)
    DL = _C_zz(DN, Cmz, lam, DC, DH, inv_wy)

    # ── Dénominateur commun (1−NEd/Ncr_min) ──────────────────────────
    denom_k = 1.0 - NEd_c / Ncr_min if Ncr_min > 0 else 1.0

    # ── k carbone (CY, CZ, DA, DB) ────────────────────────────────────
    if classe <= 2:
        kyy = Cmy * CmLT * DO / denom_k / DI
        kyz = Cmz * DO  / denom_k * (1.0/DJ) * 0.6 * (DN/DM) ** 0.5
        kzy = Cmy * CmLT * DP / denom_k * (1.0/DK) * 0.6 * (DM/DN) ** 0.5
        kzz = Cmz * DP  / denom_k / DL
    else:  # classe 3
        kyy = Cmy * CmLT * DO / denom_k
        kyz = Cmz * DO  / denom_k
        kzy = Cmy * CmLT * DP / denom_k
        kzz = Cmz * DP  / denom_k

    # ── k inox (DU, DV, DW) ───────────────────────────────────────────
    DW = 1.0   # constante $DW$56
    if Nb_Rd_y and Nb_Rd_y > 0:
        DU = min(max(1.2, 1.0 + 2.0*(lam-0.5)*NEd_c/Nb_Rd_y),
                 1.2 + 2.0*NEd_c/Nb_Rd_y)
    else:
        DU = 1.2
    if Nb_Rd_z and Nb_Rd_z > 0:
        DV = min(max(1.2, 1.0 + 2.0*(lam-0.5)*NEd_c/Nb_Rd_z),
                 1.2 + 2.0*NEd_c/Nb_Rd_z)
    else:
        DV = 1.2

    # ── Résistances pour CW/CX ────────────────────────────────────────
    # Nb,Rd,min (compression) — CW utilise l'axe gouvernant
    Nb_y = Nb_Rd_y or 1e12
    Nb_z = Nb_Rd_z or 1e12
    Nb_TF = Nb_Rd_TF or 1e12
    if section_type == "U":
        Nb_min_CW = min(Nb_y, Nb_z, Nb_TF)
    else:
        Nb_min_CW = Nb_y    # CW utilise CH (Nb,Rd,y) pour H, O, X

    # Résistance My dans CW : Mb,Rd si LTB disponible, sinon My,c,Rd
    has_ltb = (section_type in ("H", "U")) and (Mb_Rd is not None) and not is_stainless
    M_Rd_y_CW = Mb_Rd if has_ltb else My_c_Rd   # dénominateur du terme My dans CW

    # Résistance My dans CX : Mb,Rd pour H (carbone et inox), My,c,Rd sinon
    has_Mb_CX = (section_type in ("H", "U")) and (Mb_Rd is not None)
    M_Rd_y_CX = Mb_Rd if has_Mb_CX else My_c_Rd

    # γM0/γM1 pour les résistances section (Mz,c,Rd est stocké avec γM1)
    gM_ratio = gM0 / gM1

    def _ratio_comb(Nb_Rd_denom: float, k_y: float, M_y_denom: float,
                    k_z: float, My_denom_override: Optional[float] = None) -> float:
        """Calcule ROUNDUP(NEd/Nb + |ky·My/M_y| + |kz·Mz/(Mz_c·gM)| , 2)"""
        term_N  = NEd_c / Nb_Rd_denom
        M_y_den = My_denom_override if My_denom_override is not None else M_y_denom
        term_My = abs(k_y * My_Ed / M_y_den) if abs(M_y_den) > 0 else 0.0
        term_Mz = abs(k_z * Mz_Ed / (Mz_c_Rd * gM_ratio)) if abs(Mz_c_Rd) > 0 else 0.0
        raw = term_N + term_My + term_Mz
        # ROUNDUP(x, 2) = ceil(x * 100) / 100
        import math as _m
        return _m.ceil(raw * 100) / 100

    # ── CW ────────────────────────────────────────────────────────────
    if NEd_c == 0.0 and section_type in ("O", "X"):
        ratio_CW = 0.0
    elif is_stainless:
        ratio_CW = _ratio_comb(Nb_min_CW, DU, My_c_Rd * gM0, DV)
    else:
        ratio_CW = _ratio_comb(Nb_min_CW, kyy, M_Rd_y_CW, kyz)

    # ── CX ────────────────────────────────────────────────────────────
    if NEd_c == 0.0 and section_type in ("O", "X"):
        ratio_CX = 0.0
    elif is_stainless:
        ratio_CX = _ratio_comb(Nb_z, DW, M_Rd_y_CX, DV)
    else:
        ratio_CX = _ratio_comb(Nb_z, kzy, M_Rd_y_CX, kzz)

    return {
        "DC": DC, "DD": DD, "DM": DM, "DN": DN,
        "DO": DO, "DP": DP,
        "DE": DE, "DF": DF, "DG": DG, "DH": DH,
        "DI": DI, "DJ": DJ, "DK": DK, "DL": DL,
        "kyy": kyy, "kyz": kyz, "kzy": kzy, "kzz": kzz,
        "DU": DU, "DV": DV, "DW": DW,
        "ratio_CW": ratio_CW,
        "ratio_CX": ratio_CX,
    }
