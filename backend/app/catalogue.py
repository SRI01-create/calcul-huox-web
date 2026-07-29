"""
Phase 2 — Chargement et lookup des catalogues de sections.

Charge les 4 CSV (H, U, O, X) en mémoire au démarrage de l'application.
Fournit un accès O(1) aux propriétés géométriques de ~1 171 sections.

Fonctions publiques
-------------------
    preload_all()                          → pré-charge les 4 catalogues
    get_section(cat_type, designation)     → dict complet des propriétés
    list_sections(cat_type, query="")      → liste de désignations filtrées
    detect_subtype(cat_type, designation)  → dict de flags de forme

Sous-types détectés
-------------------
    H : is_welded (préfixe "s")
    U : is_welded, is_angle ("L ")
    O : is_circular ("Tci"), is_square ("Tca"), is_rectangular ("Tre"), is_welded
    X : is_circular ("Pci"), is_square ("Pca"), is_rectangular ("Pre")
        (toutes les sections X sont soudées)

Unités des propriétés retournées
---------------------------------
    h, b, tw, tf, r, d, t       : mm
    iy, iz, ys, ym              : mm   (U seulement)
    A, Av_y, Av_z               : m²
    Iy, Iz, It                  : m⁴
    Wel_y, Wpl_y, Wel_z, Wpl_z  : m³
    IW                          : m⁶
    Sw  (H) / Sw_w (U)          : m⁴
    b   pour Tci / Pci          : None (section circulaire)
    Wpl_y / Wpl_z pour cornières : None (utiliser Wel)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

# ─── Chemin vers les CSV ─────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Types de catalogue valides
VALID_TYPES = ("H", "U", "O", "X")

# ─── Cache des DataFrames (chargés une seule fois) ───────────────────────────
_CATALOGUES: dict[str, pd.DataFrame] = {}


def _load_df(cat_type: str) -> pd.DataFrame:
    """
    Charge le CSV d'un catalogue dans un DataFrame indexé par désignation.
    Les cellules vides deviennent NaN (puis None dans get_section).
    """
    path = _DATA_DIR / f"catalogue_{cat_type}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Catalogue {cat_type} introuvable : {path}\n"
            "Exécuter : python backend/scripts/extract_catalogues.py --xlsm <fichier.xlsm>"
        )
    df = pd.read_csv(path, dtype={"designation": str}, keep_default_na=True)

    # Forcer le type numérique sur toutes les colonnes sauf la désignation
    num_cols = [c for c in df.columns if c != "designation"]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce")

    # Index sur la désignation (lookup O(1))
    df = df.set_index("designation")
    return df


def _get_df(cat_type: str) -> pd.DataFrame:
    """Retourne le DataFrame du catalogue, en le chargeant si absent du cache."""
    if cat_type not in _CATALOGUES:
        _CATALOGUES[cat_type] = _load_df(cat_type)
    return _CATALOGUES[cat_type]


# ─── Pré-chargement (appelé au démarrage FastAPI) ────────────────────────────

def preload_all() -> None:
    """
    Pré-charge les 4 catalogues en mémoire.
    À appeler dans le gestionnaire de démarrage FastAPI (Phase 18) :

        @app.on_event("startup")
        async def startup():
            from app.catalogue import preload_all
            preload_all()
    """
    for t in VALID_TYPES:
        _get_df(t)


# ─── Détection du sous-type ──────────────────────────────────────────────────

def detect_subtype(cat_type: str, designation: str) -> dict:
    """
    Retourne les flags de forme d'une section à partir de sa désignation.

    Ces flags pilotent les choix de formules dans le moteur de calcul :
      - is_welded      → courbe de déversement c/d au lieu de a/b (§6.3.2.3 NA)
      - is_circular    → formules spécifiques (Tci : Bredt circ. / Pci : Timoshenko circ.)
      - is_square      → tube creux carré (Bredt rect.) ou plein carré
      - is_rectangular → tube creux rect. (Bredt rect.) ou plein rect.
      - is_angle       → cornière : Wpl non disponible, déversement limité

    Retour
    ------
    dict avec clés : is_welded, is_angle, is_circular, is_square, is_rectangular
    """
    d = designation.strip()
    flags: dict[str, bool] = {
        "is_welded":      d.startswith("s "),
        "is_angle":       False,
        "is_circular":    False,
        "is_square":      False,
        "is_rectangular": False,
    }

    if cat_type == "U":
        # Cornière : "L " après le préfixe optionnel "s "
        core = d[2:] if d.startswith("s ") else d
        flags["is_angle"] = core.upper().startswith("L ")

    elif cat_type == "O":
        flags["is_circular"]    = "Tci" in d
        flags["is_square"]      = "Tca" in d
        flags["is_rectangular"] = "Tre" in d

    elif cat_type == "X":
        flags["is_circular"]    = "Pci" in d
        flags["is_square"]      = "Pca" in d
        flags["is_rectangular"] = "Pre" in d

    return flags


# ─── Accès aux propriétés d'une section ──────────────────────────────────────

def get_section(cat_type: str, designation: str) -> dict:
    """
    Retourne les propriétés géométriques complètes d'une section.

    Paramètres
    ----------
    cat_type    : "H" | "U" | "O" | "X"
    designation : désignation exacte du catalogue (ex. "IPE 200", "Tci 88.9 x 4")

    Retour
    ------
    dict contenant :
      - "cat_type"    : str
      - "designation" : str
      - toutes les colonnes du CSV (float ou None si cellule vide)
      - flags de detect_subtype()

    Lève
    ----
    ValueError     si cat_type invalide
    KeyError       si la désignation est inconnue dans le catalogue
    FileNotFoundError si le CSV est absent (extract_catalogues.py non exécuté)

    Remarques
    ---------
    - b = None pour les sections circulaires (Tci, Pci)
    - Wpl_y / Wpl_z = None pour les cornières (L) → utiliser Wel_y / Wel_z
    - d = None pour les cornières (pas d'âme pleine continue)
    - r = 0.0 pour les sections PRS (is_welded = True)
    """
    if cat_type not in VALID_TYPES:
        raise ValueError(f"Type de catalogue invalide : '{cat_type}'. Valeurs : {VALID_TYPES}")

    df = _get_df(cat_type)

    if designation not in df.index:
        # Suggestion partielle pour aider au diagnostic
        suggestions = [s for s in df.index if designation[:6].lower() in s.lower()][:3]
        hint = f" Suggestions : {suggestions}" if suggestions else ""
        raise KeyError(
            f"Section '{designation}' introuvable dans le catalogue {cat_type}.{hint}"
        )

    row = df.loc[designation]
    props: dict = {"cat_type": cat_type, "designation": designation}

    # NaN → None, float sinon
    for col, val in row.items():
        props[col] = None if pd.isna(val) else float(val)

    # Flags de forme
    props.update(detect_subtype(cat_type, designation))

    return props


# ─── Liste des désignations (pour les dropdowns du frontend) ─────────────────

def list_sections(cat_type: str, query: str = "") -> list[str]:
    """
    Retourne les désignations du catalogue, filtrées par un mot-clé.

    Paramètres
    ----------
    cat_type : "H" | "U" | "O" | "X"
    query    : filtre optionnel, insensible à la casse (sous-chaîne)
               Ex. "IPE", "HEA", "Tci", "UPE"

    Retour
    ------
    Liste de désignations triées alphabétiquement.
    """
    if cat_type not in VALID_TYPES:
        raise ValueError(f"Type invalide : '{cat_type}'")

    df = _get_df(cat_type)
    designations: list[str] = df.index.tolist()

    if query:
        q = query.strip().lower()
        designations = [d for d in designations if q in d.lower()]

    return sorted(designations)
