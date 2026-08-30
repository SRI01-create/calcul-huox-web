"""
Phase 29 — Guide de choix des courbes de flambement (Table 6.2 EC3 + EN 1993-1-4).

Transcription directe du document fourni par l'utilisateur
("règles_de_choix_des_courbes_de_flambement.docx"), sans réinterprétation.

Ce module n'est JAMAIS appelé par les moteurs de calcul (engine_H/U/O/X.py) :
il ne sert qu'à alimenter une suggestion, dans l'écran de configuration RC,
que l'utilisateur reste entièrement libre de suivre ou d'ignorer. Les champs
RCConfig.bc_* qui pilotent ce module sont purement indicatifs — voir
models.py. Les courbes réellement utilisées par le calcul restent
RCConfig.buckling_curve_y / buckling_curve_z, renseignées indépendamment.

Fonctions publiques
-------------------
    suggest_curves_H(steel_family, fabrication, h, b, tf) → (curve_y, curve_z)
    suggest_curves_U(shape, material, fabrication) → (curve_y, curve_z)
    suggest_curves_O(steel_family, shape, b, h, t) → (curve_y, curve_z)
    suggest_curves_X() → (curve_y, curve_z)

Chaque fonction lève ValueError si un paramètre est manquant ou invalide
pour la combinaison demandée (ex. `shape` absent pour un O carbone) — le
message précise exactement quel choix il manque, pour affichage direct côté
frontend.
"""

from __future__ import annotations

STEEL_FAMILIES = ("s235_s420", "s460", "inox")
U_SHAPES = ("profile", "corniere")
U_MATERIALS = ("carbone", "inox", "inox_forme_a_froid")
O_SHAPES = ("creuse_chaud", "creuse_froid", "caisson_soude", "caisson_soude_a_sup_05tf")
FABRICATIONS = ("L", "S")


def _check_choice(value: str | None, allowed: tuple[str, ...], field_name: str) -> str:
    if value not in allowed:
        raise ValueError(
            f"{field_name} manquant ou invalide : attendu l'une des valeurs "
            f"{allowed}, reçu {value!r}."
        )
    return value


# ─── H ────────────────────────────────────────────────────────────────────────

def suggest_curves_H(
    steel_family: str, fabrication: str, h: float, b: float, tf: float,
) -> tuple[str, str]:
    """
    Table 6.2 EC3 (§6.3.1.2) — sections en I/H, laminées ou soudées (PRS).
    steel_family : "s235_s420" | "s460" | "inox"
    fabrication  : "L" (laminé) | "S" (PRS/soudé)
    h, b, tf     : mm (issus du catalogue — pas de saisie utilisateur)
    """
    _check_choice(steel_family, STEEL_FAMILIES, "steel_family")
    _check_choice(fabrication, FABRICATIONS, "fabrication")
    if h is None or b is None or tf is None or b == 0:
        raise ValueError("Géométrie (h, b, tf) indisponible pour cette désignation.")

    hb_gt_1_2 = (h / b) > 1.2

    if steel_family == "s235_s420":
        if fabrication == "L":
            if hb_gt_1_2:
                return ("a", "b") if tf <= 40 else ("b", "c")
            else:
                return ("b", "c") if tf <= 100 else ("d", "d")
        else:  # PRS
            return ("b", "c") if tf <= 40 else ("c", "d")

    if steel_family == "s460":
        if fabrication == "L":
            if hb_gt_1_2:
                return ("a0", "a0") if tf <= 40 else ("a", "a")
            else:
                return ("a", "a") if tf <= 100 else ("c", "c")
        else:  # PRS
            return ("b", "c") if tf <= 40 else ("c", "d")

    # inox
    if fabrication == "L":
        if hb_gt_1_2:
            return ("a", "b") if tf <= 40 else ("b", "c")
        else:
            return ("b", "c") if tf <= 100 else ("d", "d")
    else:  # PRS — pas de distinction d'épaisseur dans le document
        return ("c", "d")


# ─── U ────────────────────────────────────────────────────────────────────────

def suggest_curves_U(
    shape: str, material: str, fabrication: str | None = None,
) -> tuple[str, str]:
    """
    shape        : "profile" (profilé U) | "corniere"
    material     : "carbone" | "inox" | "inox_forme_a_froid"
    fabrication  : "L" | "S" — requis uniquement si material == "inox"
    """
    _check_choice(shape, U_SHAPES, "shape")
    _check_choice(material, U_MATERIALS, "material")

    if material == "inox":
        _check_choice(fabrication, FABRICATIONS, "fabrication")

    if shape == "profile":
        if material == "carbone":
            return ("c", "c")
        if material == "inox":
            return ("c", "c") if fabrication == "L" else ("c", "d")
        return ("c", "c")  # inox_forme_a_froid

    # corniere
    if material == "carbone":
        return ("b", "b")
    if material == "inox":
        return ("b", "b") if fabrication == "L" else ("c", "d")
    return ("c", "c")  # inox_forme_a_froid


# ─── O ────────────────────────────────────────────────────────────────────────

def suggest_curves_O(
    steel_family: str, shape: str | None, b: float | None, h: float | None, t: float | None,
) -> tuple[str, str]:
    """
    steel_family : "s235_s420" | "s460" | "inox"
    shape        : "creuse_chaud" | "creuse_froid" | "caisson_soude" |
                   "caisson_soude_a_sup_05tf" — requis sauf si steel_family == "inox"
    b, h, t      : mm (issus du catalogue) — utilisés uniquement pour le sous-cas
                   "caisson_soude_a_sup_05tf" (b/tf et h/tw, Table 6.2). Le
                   catalogue O n'ayant qu'une épaisseur de paroi unique `t`
                   (pas de tf/tw séparés), b/t et h/t sont utilisés à la place —
                   validé avec l'utilisateur (approximation raisonnable pour une
                   section à épaisseur uniforme).
    """
    _check_choice(steel_family, STEEL_FAMILIES, "steel_family")

    if steel_family == "inox":
        return ("c", "c")

    _check_choice(shape, O_SHAPES, "shape")

    if shape == "caisson_soude_a_sup_05tf":
        if b is None or h is None or t is None or t == 0:
            raise ValueError("Géométrie (b, h, t) indisponible pour cette désignation.")
        thin_walled = (b / t) < 30 and (h / t) < 30

    if steel_family == "s235_s420":
        if shape == "creuse_chaud":
            return ("a", "a")
        if shape == "creuse_froid":
            return ("c", "c")
        if shape == "caisson_soude":
            return ("b", "b")
        return ("c", "c") if thin_walled else ("b", "b")

    # s460
    if shape == "creuse_chaud":
        return ("a0", "a0")
    if shape == "creuse_froid":
        return ("c", "c")
    if shape == "caisson_soude":
        return ("b", "b")
    return ("c", "c") if thin_walled else ("b", "b")


# ─── X ────────────────────────────────────────────────────────────────────────

def suggest_curves_X() -> tuple[str, str]:
    """Sections pleines — toujours c/c, aucun choix."""
    return ("c", "c")
