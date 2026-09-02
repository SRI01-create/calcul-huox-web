"""
Phase 2 — Chargement et lookup des catalogues de sections.
Phase 30 — Flags de forme (is_welded/is_angle/is_circular) désormais stockés
directement en colonnes dans les CSV, au lieu d'être déduits du texte de la
désignation (archaïsme hérité du classeur Excel d'origine — cf. REPRISE.md).

Charge les 4 CSV (H, U, O, X) en mémoire au démarrage de l'application.
Fournit un accès O(1) aux propriétés géométriques de ~1 171 sections.

Fonctions publiques
-------------------
    preload_all()                          → pré-charge les 4 catalogues
    get_section(cat_type, designation)     → dict complet des propriétés
    list_sections(cat_type, query="")      → liste de désignations filtrées

Flags de forme stockés (colonnes CSV, 0/1 → bool)
--------------------------------------------------
    H : is_welded
    U : is_welded, is_angle
    O : is_welded, is_circular
    X : is_welded, is_circular

    (is_square/is_rectangular ont existé un temps mais n'étaient consommés
    par aucune formule — supprimés en Phase 30.)

Unités des propriétés retournées
---------------------------------
    h, b, tw, tf, r, d, t       : mm
    iy, iz, ys, ym              : mm   (U seulement)
    A, Av_y, Av_z               : m²
    Iy, Iz, It                  : m⁴
    Wel_y, Wpl_y, Wel_z, Wpl_z  : m³
    IW                          : m⁶
    Sw  (H) / Sw_w (U)          : m⁴
    b   pour sections circulaires : None
    Wpl_y / Wpl_z pour cornières : None (utiliser Wel)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

# ─── Chemin vers les CSV ─────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Colonnes booléennes (0/1 en CSV) — castées explicitement, pas via to_numeric seul
_FLAG_COLUMNS = ("is_welded", "is_angle", "is_circular")

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
      - toutes les colonnes du CSV (float ou None si cellule vide), à
        l'exception des colonnes de flags (is_welded/is_angle/is_circular),
        castées en bool — présentes seulement pour les types où elles ont
        un sens (ex. "is_angle" absent d'un dict H)

    Lève
    ----
    ValueError     si cat_type invalide
    KeyError       si la désignation est inconnue dans le catalogue
    FileNotFoundError si le CSV est absent (extract_catalogues.py non exécuté)

    Remarques
    ---------
    - b = None pour les sections circulaires
    - Wpl_y / Wpl_z = None pour les cornières (is_angle = True) → utiliser Wel_y / Wel_z
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

    # NaN → None, float sinon (colonnes de flags traitées à part ci-dessous)
    for col, val in row.items():
        if col in _FLAG_COLUMNS:
            continue
        props[col] = None if pd.isna(val) else float(val)

    # Flags de forme (0/1 en CSV) → bool, uniquement pour les colonnes
    # présentes dans ce catalogue (ex. "is_angle" n'existe pas pour H/O/X)
    for flag in _FLAG_COLUMNS:
        if flag in row.index:
            props[flag] = bool(row[flag])

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
