"""
Phase 6 — Classification de section + voilement par cisaillement + aires nettes.

Toutes les formules sont extraites directement du fichier Excel
(colonnes S, U, AO, AQ, AR, AT des feuilles H / U / O / X, ligne 61).

Fonctions publiques
-------------------
    section_class_H(h,b,tw,tf,r,d, eps, is_stainless, fabrication) → int
    section_class_U(h,b,tw,tf,r,d, designation, eps, is_stainless, fab) → int
    section_class_O(h,b,t, designation, eps, is_stainless) → int
    section_class_X() → int  (toujours 1)
    can_ignore_shear_buckling(h,tf,tw, eps, is_stainless, is_angle) → bool
    net_areas(A, A_trou, Af_trou, tf, b) → dict
    can_ignore_tension_flange_holes(Af_net,Af_trou,fy,fu,gM0,gM2,kr) → bool

Hypothèse de classification (issue de l'Excel)
-----------------------------------------------
On classe en supposant tous les éléments en COMPRESSION PURE (limites les plus
conservatives de la Table 5.2). La classe est donc indépendante des efforts.

Class 4 = hors portée de l'outil → ratios = "X" dans les résultats.

Unités
------
    h, b, tw, tf, r, d, t : mm
    A, A_trou, Af_trou    : m²
    fy, fu                : MPa
"""

from __future__ import annotations


# ─── Limites de classification extraites des formules Excel ──────────────────

# Âme (web) — col. U feuilles H et U — d/tw
_WEB_C = (33.0, 38.0, 42.0)        # carbone  ×ε  → classes 1, 2, 3
_WEB_I = (25.7, 26.7, 30.7)        # inox     ×ε

# Semelle H — col. U feuille H — c = (b−tw−2r)/(2·tf)
_FLG_H_C    = (9.0, 10.0, 14.0)    # carbone         ×ε
_FLG_H_IL   = (10.0, 10.4, 11.9)   # inox laminé (L) ×ε
_FLG_H_IS   = (9.0,  9.4, 11.0)    # inox soudé  (S) ×ε

# Semelle U (canal) — col. U feuille U — c = (b−tw−r)/tf (un seul rayon)
_FLG_U_C    = (9.0, 10.0, 14.0)    # carbone ×ε  (mêmes que H)
_FLG_U_IF   = (10.0, 10.4, 11.9)   # inox formé à froid (F) ×ε
_FLG_U_IS   = (9.0,  9.4, 11.0)    # inox soudé (S) ×ε
# inox laminé (L) → classe 1 directe (règle spéciale, formule Excel)

# Cornières — col. U feuille U — IF(FIND("L ", designation))
_ANG_C  = (15.0, 11.5)   # carbone : h/tw ≤ 15ε  AND (h+b)/(tw+tf) ≤ 11.5ε → 3
_ANG_I  = (11.9,  9.1)   # inox    : h/tw ≤ 11.9ε AND (h+b)/(tw+tf) ≤ 9.1ε  → 3

# Tubes creux circulaires Tci — col. U feuille O — D/t vs ε² (carré !)
_CHS = (50.0, 70.0, 90.0)           # ×ε²  → classes 1, 2, 3 ; sinon 4

# Tubes creux rectangulaires/carrés Tca, Tre — (max(h,b)−2t)/t
# Mêmes constantes que l'âme H : _WEB_C et _WEB_I


# ─── Utilitaire interne ───────────────────────────────────────────────────────

def _cls(ratio: float, lims: tuple, factor: float) -> int:
    """Retourne 1, 2, 3 ou 4 selon ratio ≤ lims[i] × factor."""
    if ratio <= lims[0] * factor: return 1
    if ratio <= lims[1] * factor: return 2
    if ratio <= lims[2] * factor: return 3
    return 4


# ─── Section class H ─────────────────────────────────────────────────────────

def section_class_H(
    h: float, b: float, tw: float, tf: float, r: float, d: float,
    eps: float,
    is_stainless: bool,
    fabrication: str = "L",   # "L" = laminé · "S" = PRS soudé
) -> int:
    """
    Classe de section pour profils H/I (IPE, HEA, HEB, IPN, PRS H…).

    Source Excel : colonne U feuille H ligne 61
    -------------------------------------------
    Âme    : c/t = d / tw
    Semelle: c/t = (b − tw − 2r) / (2 · tf)
    Classe = MAX(classe âme, classe semelle)

    Limites carbone (Table 5.2) :
      Âme    : 33ε / 38ε / 42ε
      Semelle: 9ε  / 10ε / 14ε

    Limites inox (EN 1993-1-4 Table 5.2) :
      Âme    : 25.7ε / 26.7ε / 30.7ε
      Semelle (L) : 10ε / 10.4ε / 11.9ε
      Semelle (S) : 9ε  / 9.4ε  / 11ε
    """
    web_cls = _cls(d / tw, _WEB_I if is_stainless else _WEB_C, eps)

    c_flange = (b - tw - 2.0 * r) / (2.0 * tf)
    if is_stainless:
        flg_lims = _FLG_H_IS if fabrication == "S" else _FLG_H_IL
    else:
        flg_lims = _FLG_H_C
    flg_cls = _cls(c_flange, flg_lims, eps)

    return max(web_cls, flg_cls)


# ─── Section class U ─────────────────────────────────────────────────────────

def section_class_U(
    h: float, b: float, tw: float, tf: float | None,
    r: float | None, d: float | None,
    designation: str,
    eps: float,
    is_stainless: bool,
    fabrication: str = "L",
) -> int:
    """
    Classe de section pour profils U (UPN, UPE, PRS U) et cornières (L).

    Source Excel : colonne U feuille U ligne 61
    -------------------------------------------
    Détection cornière : FIND("L ", désignation) — note l'espace après "L"

    Cornière : classes 3 ou 4 uniquement (EC3)
        Carbon : h/tw ≤ 15ε  ET (h+b)/(tw+tf) ≤ 11.5ε  → 3 ; sinon 4
        Inox   : h/tw ≤ 11.9ε ET (h+b)/(tw+tf) ≤ 9.1ε   → 3 ; sinon 4

    Canal (UPN, UPE…) :
        Âme    : d / tw          (mêmes limites que H)
        Semelle: (b − tw − r) / tf  (un seul rayon de raccordement)
        Carbone : 9ε / 10ε / 14ε
        Inox L  : classe 1 directe (règle Excel)
        Inox S  : 9ε / 9.4ε / 11ε
        Inox F  : 10ε / 10.4ε / 11.9ε
        Classe = MAX(âme, semelle)
    """
    is_angle = "L " in designation       # FIND("L ", T61) dans Excel

    if is_angle:
        tf_eff = tw if (tf is None) else tf
        r1 = h / tw
        r2 = (h + b) / (tw + tf_eff)
        lim1, lim2 = _ANG_I if is_stainless else _ANG_C
        return 3 if (r1 <= lim1 * eps and r2 <= lim2 * eps) else 4

    # Canal
    web_cls = _cls(d / tw, _WEB_I if is_stainless else _WEB_C, eps)

    r_eff  = 0.0 if r  is None else r
    tf_eff = tw  if tf is None else tf
    c_flg  = (b - tw - r_eff) / tf_eff

    if is_stainless:
        if fabrication not in ("F", "S"):   # "L" laminé → classe 1 (règle Excel)
            flg_cls = 1
        elif fabrication == "S":
            flg_cls = _cls(c_flg, _FLG_U_IS, eps)
        else:                               # "F" formé à froid
            flg_cls = _cls(c_flg, _FLG_U_IF, eps)
    else:
        flg_cls = _cls(c_flg, _FLG_U_C, eps)

    return max(web_cls, flg_cls)


# ─── Section class O ─────────────────────────────────────────────────────────

def section_class_O(
    h: float, b: float | None, t: float,
    designation: str,
    eps: float,
    is_stainless: bool,
) -> int:
    """
    Classe de section pour profils creux O (Tca, Tre, Tci).

    Source Excel : colonne U feuille O ligne 61
    -------------------------------------------
    Tci (circulaire) : D/t ≤ {50·ε² / 70·ε² / 90·ε²} → {1/2/3} ; sinon 4
        Note : l'Excel retourne "X" (string) au lieu de 4 pour les Tci
        dépassant la classe 3. On retourne 4 (int) pour uniformiser.

    Tca / Tre : (max(h, b) − 2t) / t
        Carbone : 33ε / 38ε / 42ε
        Inox    : 25.7ε / 26.7ε / 30.7ε
    """
    if "Tci" in designation:
        return _cls(h / t, _CHS, eps ** 2)     # ε² ici !
    else:
        b_eff = h if b is None else b
        ratio = (max(h, b_eff) - 2.0 * t) / t
        return _cls(ratio, _WEB_I if is_stainless else _WEB_C, eps)


# ─── Section class X ─────────────────────────────────────────────────────────

def section_class_X() -> int:
    """
    Classe de section pour profils pleins X (Pca, Pre, Pci).

    Source Excel : feuille X, U = $U$39 = 1 (valeur fixe codée en dur).
    Les sections pleines sont toujours Classe 1.
    """
    return 1


# ─── Voilement par cisaillement ───────────────────────────────────────────────

def can_ignore_shear_buckling(
    h: float, tf: float, tw: float,
    eps: float,
    is_stainless: bool,
    is_angle: bool = False,
) -> bool:
    """
    Retourne True si le voilement par cisaillement peut être négligé.

    Source Excel : colonne AO feuilles H et U ligne 61
    ---------------------------------------------------
    Cornière (is_angle) : toujours True — Excel retourne "" (non applicable)
    Carbone  : (h − 2·tf) / tw ≤ 72ε  → True
    Inox     : (h − 2·tf) / tw ≤ 52ε / 1.2 → True

    La formule utilise (h−2tf) comme approximation de hw (hauteur d'âme),
    conservatrice car elle ignore les rayons de raccordement.
    Pour les sections O et X : non applicable (pas de colonne AO dans ces feuilles).
    """
    if is_angle:
        return True
    ratio = (h - 2.0 * tf) / tw
    if is_stainless:
        return ratio <= 52.0 * eps / 1.2
    else:
        return ratio <= 72.0 * eps


# ─── Aires nettes ─────────────────────────────────────────────────────────────

def net_areas(
    A: float,
    A_trou: float,
    Af_trou: float,
    tf: float,
    b: float,
) -> dict:
    """
    Calcule les aires nettes pour les sections trouées.

    Source Excel : colonnes AR et AT feuilles H/U/O/X
    --------------------------------------------------
    AR = AB − AS  →  Anet   = A − A_trou
    AT = Y·0.001·W·0.001 − AU  →  Af_net = tf·b·1e-6 − Af_trou

    Paramètres
    ----------
    A       : aire brute totale (m²)
    A_trou  : aire totale des trous (m²)
    Af_trou : aire des trous dans la semelle tendue (m²)
    tf, b   : épaisseur et largeur de la semelle tendue (mm)

    Retour
    ------
    dict : Anet (m²), Af (m²), Af_net (m²)
    """
    Anet   = A - A_trou
    Af     = tf * 1e-3 * b * 1e-3    # tf[mm] × b[mm] → m²
    Af_net = Af - Af_trou
    return {"Anet": Anet, "Af": Af, "Af_net": Af_net}


def can_ignore_tension_flange_holes(
    Af_net: float,
    Af_trou: float,
    fy: float,
    fu: float,
    gamma_M0: float,
    gamma_M2: float,
    kr: float = 0.9,
) -> bool:
    """
    Retourne True si les trous en semelle tendue peuvent être ignorés (§6.2.5(4)).

    Source Excel : colonne AQ feuilles H/U/O/X
    -------------------------------------------
    AT·0.9·fu/γM2 ≥ (AT+AU)·fy/γM0
    → Af_net·kr·fu/γM2 ≥ Af·fy/γM0

    kr = 0.9 pour acier carbone ; valeur paramétrable pour l'inox.
    """
    Af = Af_net + Af_trou
    return Af_net * kr * fu / gamma_M2 >= Af * fy / gamma_M0
