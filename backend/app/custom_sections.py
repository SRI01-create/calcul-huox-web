"""
Phase 32 — Formules d'aide pour les sections personnalisées (hors catalogue).

Contexte
--------
L'utilisateur peut définir une section "sur mesure" (RCConfig.custom_section)
au lieu de choisir une désignation du catalogue. Certaines des grandeurs
demandées se calculent simplement à partir des dimensions déjà saisies —
Sem a fourni les formules à utiliser (formules_prop_sections.docx) :
volontairement simples (pas les formules EC3 exactes avec congés de
raccordement, coefficients de cisaillement précis, etc.), et c'est un choix
assumé, pas une approximation à améliorer.

Ces fonctions ne sont *jamais* appelées automatiquement pendant un calcul —
elles n'alimentent que l'endpoint de suggestion (POST /api/custom-section/
suggest), qui affiche une valeur suggérée dans le formulaire avec un bouton
"Appliquer" (même principe que le guide de courbes de flambement, Phase 29).
La valeur réellement utilisée pour le calcul est toujours celle du champ,
que l'utilisateur l'ait tapée lui-même ou copiée depuis la suggestion.

Convention d'unités
--------------------
Toutes les fonctions prennent les dimensions brutes (h, b, tw, tf, r, t, ys)
en mm — la même unité que RCConfig.custom_section et que le catalogue — et
renvoient le résultat directement dans l'unité interne utilisée par
catalogue.get_section() (m² pour A/Av, m⁴ pour Iy/Iz/It/Sw, m³ pour
Wel/Wpl, mm pour iy/iz). Aucune conversion n'est nécessaire côté appelant.
"""

from __future__ import annotations

import math

MM2_TO_M2 = 1e-6
MM3_TO_M3 = 1e-9
MM4_TO_M4 = 1e-12


# ── H et U : hauteur d'âme droite ────────────────────────────────────────────

def clear_web_height_mm(h_mm: float, tf_mm: float, r_mm: float) -> float:
    """d = h - 2·tf - 2·r (mm). Sections H et U (hors cornières)."""
    return h_mm - 2 * tf_mm - 2 * r_mm


# ── Aires de cisaillement — H et U ───────────────────────────────────────────

def shear_area_flange_m2(b_mm: float, tf_mm: float) -> float:
    """Av,y = 2·b·tf (aire des deux semelles). Sections H et U."""
    return 2 * b_mm * tf_mm * MM2_TO_M2


def shear_area_web_m2(h_mm: float, tw_mm: float) -> float:
    """Av,z = h·tw (aire de l'âme). Sections H et U."""
    return h_mm * tw_mm * MM2_TO_M2


# ── Moment sectoriel (contrainte de gauchissement) ───────────────────────────

def warping_statical_moment_H_m4(b_mm: float, h_mm: float, tf_mm: float) -> float:
    """Sw = b²·((h-2tf)+tf)·(tf/16) = b²·(h-tf)·tf/16. Section H."""
    Sw_mm4 = (b_mm ** 2) * (h_mm - tf_mm) * (tf_mm / 16)
    return Sw_mm4 * MM4_TO_M4


def warping_statical_moment_U_m4(b_mm: float, h_mm: float, tf_mm: float, ys_mm: float) -> float:
    """
    Sw,w = 0.25·(1 - ys/b)²·b²·h·tf. Section U.

    ys : distance âme → centre de cisaillement (mm) — ne sert qu'à ce calcul,
    n'est stocké nulle part ailleurs (cf. discussion "ys jamais utilisé").
    """
    Sw_w_mm4 = 0.25 * (1 - ys_mm / b_mm) ** 2 * (b_mm ** 2) * h_mm * tf_mm
    return Sw_w_mm4 * MM4_TO_M4


# ── Rayons de giration — U ────────────────────────────────────────────────────

def radius_of_gyration_mm(I_m4: float, A_m2: float) -> float:
    """iy ou iz = √(I/A), converti en mm. Section U."""
    return math.sqrt(I_m4 / A_m2) * 1000


# ── Aires de cisaillement — O (sections creuses) ─────────────────────────────

def shear_area_O_rect_m2(A_m2: float, b_mm: float, h_mm: float) -> tuple[float, float]:
    """Av,y = A·b/(b+h) ; Av,z = A·h/(b+h). O non ronde (rectangulaire/carrée)."""
    Av_y = A_m2 * b_mm / (b_mm + h_mm)
    Av_z = A_m2 * h_mm / (b_mm + h_mm)
    return Av_y, Av_z


def shear_area_O_round_m2(A_m2: float) -> float:
    """Av,y = Av,z = 2·A/π. O ronde (tube circulaire)."""
    return 2 * A_m2 / math.pi


# ── Propriétés complètes — X (sections pleines) ──────────────────────────────

def solid_rect_properties(h_mm: float, b_mm: float) -> dict:
    """A, Iy, Iz, Wel,y, Wel,z, Av,y, Av,z pour un rectangle plein. Section X."""
    A_mm2 = h_mm * b_mm
    Iy_mm4 = (b_mm * h_mm ** 3) / 12
    Iz_mm4 = (b_mm ** 3 * h_mm) / 12
    Wel_y_mm3 = Iy_mm4 / (h_mm / 2)
    Wel_z_mm3 = Iz_mm4 / (b_mm / 2)
    Av_mm2 = (2 / 3) * h_mm * b_mm
    return {
        "A": A_mm2 * MM2_TO_M2,
        "Iy": Iy_mm4 * MM4_TO_M4,
        "Iz": Iz_mm4 * MM4_TO_M4,
        "Wel_y": Wel_y_mm3 * MM3_TO_M3,
        "Wel_z": Wel_z_mm3 * MM3_TO_M3,
        "Av_y": Av_mm2 * MM2_TO_M2,
        "Av_z": Av_mm2 * MM2_TO_M2,
    }


def solid_round_properties(h_mm: float) -> dict:
    """A, Iy, Iz, Wel,y, Wel,z, Av,y, Av,z pour un rond plein (h = diamètre). Section X."""
    r_mm = h_mm / 2
    A_mm2 = math.pi * r_mm ** 2
    I_mm4 = math.pi * h_mm ** 4 / 64
    Wel_mm3 = I_mm4 / r_mm
    Av_mm2 = (3 / 4) * A_mm2
    return {
        "A": A_mm2 * MM2_TO_M2,
        "Iy": I_mm4 * MM4_TO_M4,
        "Iz": I_mm4 * MM4_TO_M4,
        "Wel_y": Wel_mm3 * MM3_TO_M3,
        "Wel_z": Wel_mm3 * MM3_TO_M3,
        "Av_y": Av_mm2 * MM2_TO_M2,
        "Av_z": Av_mm2 * MM2_TO_M2,
    }
