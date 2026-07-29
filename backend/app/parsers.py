"""
Phase 4 — Parseurs de fichiers Ansys (format texte tabulaire).

Pourquoi whitespace-split plutôt que fixed-width
-------------------------------------------------
Le VBA Excel utilisait xlFixedWidth avec des positions de colonnes précises
car c'est la seule option d'Excel pour ce type de fichier.
En Python, split() est plus simple et tout aussi fiable : Ansys PRETAB/ETABLE
sépare toujours ses valeurs par des espaces, y compris les nombres négatifs
(ex : "  1.500E+04 -1.500E+04" ne peut pas être adjacent sans espace).

Règle de filtrage des lignes de données :
    Le premier token doit être un entier strictement positif (numéro d'élément).
    Toute ligne commençant par du texte (en-têtes, commentaires Ansys) est ignorée.

Fonctions publiques
-------------------
    parse_ele_file(content)          → DataFrame [element_id, rc_number]
    parse_lc_file(content, lc_name)  → DataFrame forces aux nœuds I et J
    build_all_lc(lc_dfs)            → DataFrame consolidé ALL_LC
    split_axial(all_lc)             → ALL_LC enrichi de NEd_t / NEd_c

Format ELE (liste des éléments)
--------------------------------
    Token 1 : numéro d'élément (int)
    Token 2 : numéro RC (int)
    Tokens suivants : ignorés

Format LC## (cas de charge, 13 tokens minimum par ligne)
---------------------------------------------------------
    Token  1 : numéro d'élément
    Token  2 : Fx_I  (N)    effort normal nœud I
    Token  3 : Fx_J  (N)    effort normal nœud J
    Token  4 : Fy_I  (N)    tranchant y nœud I
    Token  5 : Fy_J  (N)    tranchant y nœud J
    Token  6 : Fz_I  (N)    tranchant z nœud I
    Token  7 : Fz_J  (N)    tranchant z nœud J
    Token  8 : Mx_I  (N.m)  torsion nœud I
    Token  9 : Mx_J  (N.m)  torsion nœud J
    Token 10 : My_I  (N.m)  moment fléchissant y nœud I
    Token 11 : My_J  (N.m)  moment fléchissant y nœud J
    Token 12 : Mz_I  (N.m)  moment fléchissant z nœud I
    Token 13 : Mz_J  (N.m)  moment fléchissant z nœud J
    Tokens 14+ : ignorés (présents dans certaines versions Ansys)

Convention de signe — effort normal Fx
---------------------------------------
    Fx > 0 → traction  → NEd_t = Fx,  NEd_c = 0
    Fx < 0 → compression → NEd_t = 0, NEd_c = |Fx|

    Dans build_all_lc, on retient le Fx signé du nœud dominant :
    signe du nœud avec max(|Fx_I|, |Fx_J|).
    Pour un élément sans charge axiale distribuée : |Fx_I| = |Fx_J|,
    signes opposés → on prend Fx_I.

Convention — efforts tranchants, torsion, moments (Fy, Fz, Mx, My, Mz)
------------------------------------------------------------------------
    Valeur de dimensionnement = max(|valeur_I|, |valeur_J|) ≥ 0
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─── Noms des colonnes LC ─────────────────────────────────────────────────────
_LC_FORCE_COLS = [
    "Fx_I", "Fx_J",
    "Fy_I", "Fy_J",
    "Fz_I", "Fz_J",
    "Mx_I", "Mx_J",
    "My_I", "My_J",
    "Mz_I", "Mz_J",
]
_LC_ALL_COLS  = ["lc_name", "element_id"] + _LC_FORCE_COLS

# Paires I/J pour le calcul de l'enveloppe dans build_all_lc
_IJ_PAIRS  = [
    ("Fx_I", "Fx_J"),
    ("Fy_I", "Fy_J"),
    ("Fz_I", "Fz_J"),
    ("Mx_I", "Mx_J"),
    ("My_I", "My_J"),
    ("Mz_I", "Mz_J"),
]
_ENV_NAMES = ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]


# ─── Utilitaire : filtre de ligne ─────────────────────────────────────────────

def _elem_id_from_token(token: str) -> int | None:
    """
    Retourne l'entier si le token est un numéro d'élément valide (int > 0),
    None sinon.
    """
    try:
        val = int(token.strip())
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


# ─── Parseur ELE ─────────────────────────────────────────────────────────────

def parse_ele_file(content: str) -> pd.DataFrame:
    """
    Parse le fichier de liste des éléments Ansys.

    Tolère des lignes d'en-tête Ansys (ignorées), des lignes vides,
    et tout nombre de colonnes supplémentaires après le numéro RC.

    Paramètres
    ----------
    content : contenu complet du fichier (str)

    Retour
    ------
    DataFrame colonnes : element_id (int), rc_number (int)

    Lève
    ----
    ValueError — fichier vide ou sans données valides
    ValueError — numéros d'éléments en double
    """
    rows: list[dict] = []

    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        tokens = raw_line.split()
        if len(tokens) < 2:
            continue                          # ligne vide ou incomplète → ignorée

        elem_id = _elem_id_from_token(tokens[0])
        if elem_id is None:
            continue                          # en-tête ou commentaire → ignoré

        try:
            rc = int(tokens[1])
        except ValueError:
            raise ValueError(
                f"Fichier ELE ligne {lineno} : le numéro RC '{tokens[1]}' "
                "n'est pas un entier valide."
            )

        rows.append({"element_id": elem_id, "rc_number": rc})

    if not rows:
        raise ValueError(
            "Fichier ELE : aucune donnée valide trouvée.\n"
            "Format attendu : une ligne par élément, "
            "numéro d'élément en premier token, numéro RC en second token."
        )

    df = pd.DataFrame(rows)

    # Vérifier l'unicité des éléments
    dups = df["element_id"][df["element_id"].duplicated(keep=False)].unique().tolist()
    if dups:
        raise ValueError(
            f"Fichier ELE : numéros d'éléments en double → "
            f"{dups[:5]}{'…' if len(dups) > 5 else ''}"
        )

    return df[["element_id", "rc_number"]].reset_index(drop=True)


# ─── Parseur LC ──────────────────────────────────────────────────────────────

def parse_lc_file(content: str, lc_name: str) -> pd.DataFrame:
    """
    Parse un fichier de cas de charge Ansys.

    Accepte toute ligne ayant au moins 13 tokens dont le premier est un
    entier positif (numéro d'élément). Les lignes d'en-tête Ansys sont
    automatiquement ignorées.

    Paramètres
    ----------
    content  : contenu complet du fichier (str)
    lc_name  : nom du cas de charge (ex. "LC80")

    Retour
    ------
    DataFrame colonnes :
        lc_name (str), element_id (int),
        Fx_I, Fx_J, Fy_I, Fy_J, Fz_I, Fz_J,
        Mx_I, Mx_J, My_I, My_J, Mz_I, Mz_J  (float, N ou N.m)

    Lève
    ----
    ValueError — fichier vide ou sans données valides
    ValueError — un élément est présent plusieurs fois dans le même LC
    """
    rows: list[dict] = []

    for lineno, raw_line in enumerate(content.splitlines(), start=1):
        tokens = raw_line.split()

        if len(tokens) < 13:
            continue                          # en-tête, commentaire ou ligne courte

        elem_id = _elem_id_from_token(tokens[0])
        if elem_id is None:
            continue                          # premier token non numérique → ignoré

        try:
            forces = [float(tokens[i]) for i in range(1, 13)]
        except ValueError as exc:
            raise ValueError(
                f"Fichier {lc_name} ligne {lineno} : "
                f"valeur non numérique dans les colonnes forces — {exc}"
            ) from exc

        row = {"lc_name": lc_name, "element_id": elem_id}
        for col, val in zip(_LC_FORCE_COLS, forces):
            row[col] = val
        rows.append(row)

    if not rows:
        raise ValueError(
            f"Fichier {lc_name} : aucune donnée valide.\n"
            "Format attendu : au moins 13 tokens par ligne "
            "(élément + 12 composantes de forces/moments)."
        )

    df = pd.DataFrame(rows, columns=_LC_ALL_COLS)

    # Vérifier l'unicité des éléments dans ce LC
    dups = df["element_id"][df["element_id"].duplicated(keep=False)].unique().tolist()
    if dups:
        raise ValueError(
            f"Fichier {lc_name} : éléments en double → "
            f"{dups[:5]}{'…' if len(dups) > 5 else ''}"
        )

    return df.reset_index(drop=True)


# ─── Construction ALL_LC ─────────────────────────────────────────────────────

def build_all_lc(lc_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Consolide tous les DataFrames de CdC en un tableau ALL_LC.

    Une ligne par combinaison élément × cas de charge.
    Pour chaque ligne, calcule les composantes de dimensionnement :

        Fx  : effort normal signé du nœud dominant
              → signe du nœud ayant max(|Fx_I|, |Fx_J|)
              (à l'équilibre sans charge axiale distribuée : |Fx_I| = |Fx_J|,
               signes opposés → Fx = Fx_I)

        Fy, Fz, Mx, My, Mz : max(|valeur_I|, |valeur_J|) ≥ 0

    Paramètres
    ----------
    lc_dfs : dict { lc_name (str) → DataFrame de parse_lc_file() }

    Retour
    ------
    DataFrame colonnes : lc_name, element_id, Fx, Fy, Fz, Mx, My, Mz
    Trié par lc_name puis element_id.

    Lève
    ----
    ValueError — aucun cas de charge fourni
    """
    if not lc_dfs:
        raise ValueError("build_all_lc : aucun cas de charge fourni.")

    frames: list[pd.DataFrame] = []

    for lc_name, df in lc_dfs.items():
        out = pd.DataFrame({
            "lc_name":    df["lc_name"],
            "element_id": df["element_id"],
        })

        # ── Fx : signe du nœud avec la plus grande valeur absolue ────────
        # Convention : Ansys donne Fx_I et Fx_J = -Fx_I (équilibre).
        # On ramène tout à la convention nœud I (traction positive).
        # Si |Fx_J| > |Fx_I| (rare avec charge axiale distribuée),
        # on prend -Fx_J pour rester dans la convention nœud I.
        abs_I = df["Fx_I"].abs()
        abs_J = df["Fx_J"].abs()
        out["Fx"] = np.where(abs_J > abs_I, -df["Fx_J"], df["Fx_I"])

        # ── Fy, Fz, Mx, My, Mz : enveloppe max |I|, |J| ─────────────────
        for (col_I, col_J), env_name in zip(_IJ_PAIRS[1:], _ENV_NAMES[1:]):
            out[env_name] = np.maximum(df[col_I].abs(), df[col_J].abs())

        frames.append(out)

    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["lc_name", "element_id"]).reset_index(drop=True)


# ─── Décomposition NEd_t / NEd_c ─────────────────────────────────────────────

def split_axial(all_lc: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les colonnes NEd_t et NEd_c au DataFrame ALL_LC.

    NEd_t = max( Fx, 0)   — effort de traction   (N, ≥ 0)
    NEd_c = max(-Fx, 0)   — effort de compression (N, ≥ 0)

    La colonne Fx originale est conservée.

    Paramètres
    ----------
    all_lc : DataFrame issu de build_all_lc()

    Retour
    ------
    Copie de all_lc avec colonnes NEd_t et NEd_c ajoutées.
    """
    df = all_lc.copy()
    df["NEd_t"] = np.maximum( df["Fx"], 0.0)
    df["NEd_c"] = np.maximum(-df["Fx"], 0.0)
    return df
