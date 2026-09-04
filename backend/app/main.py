"""
Calcul HUOX — API FastAPI
Point d'entrée de l'application backend.

Phase 18 : endpoints /api/calculate et /api/sections.

Endpoints
─────────
    GET  /health                          → vérification de disponibilité
    GET  /api/sections/{cat_type}         → liste des désignations du catalogue
    GET  /api/sections/{cat_type}/{designation} → propriétés d'une section
    GET  /api/classification/{cat_type}/{designation} → classe de section
                                             auto-calculée (Phase 27)
    GET  /api/buckling-curve/{cat_type}/{designation} → suggestion de courbes
                                             de flambement (Phase 29)
    POST /api/calculate                   → calcul complet EC3 (Format 1 + 2)

POST /api/calculate — contrat multipart/form-data
───────────────────────────────────────────────────
    request   : str (Form)  — JSON CalculationRequest
                              {"rc_configs": [...], "material_configs": [...]}
    ele_file  : File         — fichier ELE (liste éléments → identifiant RC)
    lc_files  : list[File]   — un fichier par cas de charge Ansys
                              (le nom de cas de charge est dérivé du nom de
                              fichier sans extension, ex. "LC80.txt" → "LC80")

Réponse : CalculationResponse (Format 1 + Format 2 + métadonnées + warnings).

Erreurs
───────
    422 — JSON `request` invalide ou ne respecte pas CalculationRequest
    400 — erreur de parsing ELE/LC, désignation de section introuvable
           au catalogue
    500 — erreur de calcul inattendue

    Non bloquant (→ `warnings` dans la réponse, pas d'erreur HTTP) :
    éléments présents dans les CdC mais absents de l'ELE, ou identifiant RC
    présent dans l'ELE mais non configuré — écartés du calcul plutôt que
    de bloquer (cas des éléments d'aide à la modélisation EF : rigides,
    connecteurs, collecteurs...).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from .catalogue import VALID_TYPES, get_section, list_sections, preload_all
from .ec3.buckling_curve_guide import (
    suggest_curves_H, suggest_curves_O, suggest_curves_U, suggest_curves_X,
)
from .ec3.classification import (
    section_class_H, section_class_U, section_class_O, section_class_X,
)
from .ec3.utils import epsilon
from .models import CalculationRequest, CalculationResponse, SteelType
from .parsers import build_all_lc, parse_ele_file, parse_lc_file, split_axial
from .results import build_response

load_dotenv()

app = FastAPI(
    title="Calcul HUOX API",
    description=(
        "Post-traitement EC3 (NF EN 1993-1-1 / 1-4) "
        "pour éléments linéaires en acier issus de calculs EF Ansys."
    ),
    version="1.0.0",
)

# --- CORS ---------------------------------------------------------------
# En développement : CORS_ORIGINS=http://localhost:5173
# En production    : CORS_ORIGINS=https://calcul-huox.netlify.app
_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
origins = [o.strip() for o in _origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Démarrage ------------------------------------------------------------

@app.on_event("startup")
def _startup() -> None:
    """Précharge les catalogues CSV en mémoire (évite la latence au 1er appel)."""
    preload_all()


# --- Endpoints de base ------------------------------------------------------

@app.get("/health", tags=["monitoring"])
def health_check():
    """Vérification que l'API est en ligne."""
    return {"status": "ok", "version": "1.0.0"}


# --- Catalogues de sections --------------------------------------------------

@app.get("/api/sections/{cat_type}", tags=["sections"])
def get_sections_list(cat_type: str, query: str = ""):
    """
    Liste les désignations disponibles dans le catalogue.

    Paramètres
    ----------
    cat_type : "H" | "U" | "O" | "X"
    query    : filtre optionnel insensible à la casse (ex. "IPE", "Tci")

    Retour
    ------
    {"cat_type": ..., "count": ..., "designations": [...]}
    """
    cat_type = cat_type.upper()
    if cat_type not in VALID_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Type de catalogue invalide : '{cat_type}'. Valeurs : {VALID_TYPES}",
        )
    designations = list_sections(cat_type, query)
    return {"cat_type": cat_type, "count": len(designations), "designations": designations}


@app.get("/api/sections/{cat_type}/{designation}", tags=["sections"])
def get_section_properties(cat_type: str, designation: str):
    """
    Retourne les propriétés géométriques complètes d'une section du catalogue.

    Utilisé par le frontend pour afficher les propriétés (h, b, A, Iy, Iz…)
    lors de la sélection d'une désignation dans un RC.
    """
    cat_type = cat_type.upper()
    if cat_type not in VALID_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Type de catalogue invalide : '{cat_type}'. Valeurs : {VALID_TYPES}",
        )
    try:
        return get_section(cat_type, designation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/classification/{cat_type}/{designation}", tags=["sections"])
def get_section_classification(
    cat_type: str,
    designation: str,
    fy: float,
    E: float,
    steel_type: SteelType = SteelType.CARBON,
):
    """
    Classe de section (1 à 4) déterminée de façon conservative (compression
    pure, Table 5.2), à partir de la géométrie catalogue et des paramètres
    matériau fournis. Aucun effort interne n'entre en jeu — la classe ne
    dépend que de la section et du matériau.

    Phase 27 : utilisé par le frontend pour afficher la classe auto-calculée
    dès l'étape "1 — Configuration RC & Matériaux" (avant tout upload de
    fichiers), en amont du calcul complet — permet à l'utilisateur de décider
    s'il souhaite la forcer via RCConfig.manual_section_class.

    Phase 31 : la fabrication (laminé/PRS soudé) n'est plus un paramètre
    saisi par l'utilisateur — elle est déduite de is_welded dans le
    catalogue, pour la désignation choisie (cf. RCConfig, plus de champ
    `fabrication`).

    Paramètres
    ----------
    fy, E       : caractéristiques du matériau référencé par le RC (MPa)
    steel_type  : "carbone" | "inox"

    Retour
    ------
    {"cat_type": ..., "designation": ..., "section_class": "1"|"2"|"3"|"4"}
    """
    cat_type = cat_type.upper()
    if cat_type not in VALID_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Type de catalogue invalide : '{cat_type}'. Valeurs : {VALID_TYPES}",
        )
    try:
        sec = get_section(cat_type, designation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    is_ss = (steel_type == SteelType.STAINLESS)
    eps = epsilon(fy, E, is_ss)
    fab = "S" if sec.get("is_welded") else "L"   # Phase 31 — déduit du catalogue

    if cat_type == "H":
        classe = section_class_H(
            sec["h"], sec["b"], sec["tw"], sec["tf"], sec["r"], sec["d"], eps, is_ss, fab
        )
    elif cat_type == "U":
        classe = section_class_U(
            sec["h"], sec["b"], sec["tw"], sec["tf"], sec["r"], sec["d"],
            sec["is_angle"], eps, is_ss, fab,
        )
    elif cat_type == "O":
        classe = section_class_O(sec["h"], sec["b"], sec["t"], sec["is_circular"], eps, is_ss)
    else:  # "X"
        classe = section_class_X()

    return {"cat_type": cat_type, "designation": designation, "section_class": str(classe)}


@app.get("/api/buckling-curve/{cat_type}/{designation}", tags=["sections"])
def get_buckling_curve_suggestion(
    cat_type: str,
    designation: str,
    steel_family: Optional[str] = None,   # H, O — "s235_s420" | "s460" | "inox"
    u_shape: Optional[str] = None,        # U — "profile" | "corniere"
    u_material: Optional[str] = None,     # U — "carbone" | "inox" | "inox_forme_a_froid"
    o_shape: Optional[str] = None,        # O carbone — "creuse_chaud" | "creuse_froid" | ...
):
    """
    Suggestion de courbes de flambement (Phase 29) — transcription du document
    fourni par l'utilisateur, cf. ec3/buckling_curve_guide.py.

    Purement indicatif : ne modifie rien, ne fait qu'informer le frontend
    d'une paire (courbe y-y, courbe z-z) que l'utilisateur peut appliquer aux
    champs RCConfig.buckling_curve_y/z ou ignorer. Cet endpoint ne participe
    jamais au calcul.

    Chaque type de section n'a besoin que d'un sous-ensemble des paramètres
    (ex. o_shape n'a de sens que pour O ; ignoré silencieusement sinon).
    Les paramètres manquants pour la combinaison demandée déclenchent une
    422 avec un message précisant exactement quel choix il manque.

    Phase 31 : la fabrication (H toujours ; U si u_material == "inox") n'est
    plus un paramètre — elle est déduite de is_welded dans le catalogue.
    """
    cat_type = cat_type.upper()
    if cat_type not in VALID_TYPES:
        raise HTTPException(
            status_code=404,
            detail=f"Type de catalogue invalide : '{cat_type}'. Valeurs : {VALID_TYPES}",
        )
    try:
        sec = get_section(cat_type, designation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    fabrication = "S" if sec.get("is_welded") else "L"   # Phase 31 — déduit du catalogue

    try:
        if cat_type == "H":
            curve_y, curve_z = suggest_curves_H(
                steel_family, fabrication, sec["h"], sec["b"], sec["tf"],
            )
        elif cat_type == "U":
            curve_y, curve_z = suggest_curves_U(u_shape, u_material, fabrication)
        elif cat_type == "O":
            curve_y, curve_z = suggest_curves_O(
                steel_family, o_shape, sec["b"], sec["h"], sec["t"],
            )
        else:  # "X"
            curve_y, curve_z = suggest_curves_X()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "cat_type": cat_type, "designation": designation,
        "curve_y": curve_y, "curve_z": curve_z,
    }


# --- Calcul EC3 ---------------------------------------------------------------

def _lc_name_from_filename(filename: str | None) -> str:
    """
    Dérive le nom du cas de charge à partir du nom de fichier uploadé.

    "LC80.txt" → "LC80" · "lc_12.dat" → "lc_12" · sans extension → inchangé.
    Repli sur "LC" si filename est None ou vide (cas théorique, FastAPI
    fournit toujours un nom mais on reste défensif).
    """
    if not filename:
        return "LC"
    return Path(filename).stem


@app.post("/api/calculate", response_model=CalculationResponse, tags=["calculation"])
async def calculate(
    request: str = Form(
        ...,
        description=(
            "JSON CalculationRequest : "
            '{"rc_configs": [...], "material_configs": [...]}'
        ),
    ),
    ele_file: UploadFile = File(..., description="Fichier ELE (élément → identifiant RC)"),
    lc_files: list[UploadFile] = File(..., description="Fichiers de cas de charge Ansys"),
) -> CalculationResponse:
    """
    Calcul complet EC3 pour tous les RC fournis.

    Étapes
    ------
    1. Validation du JSON `request` → CalculationRequest (rc_configs, material_configs)
    2. Parsing du fichier ELE → mapping element_id → identifiant RC
    3. Parsing de chaque fichier LC → cas de charge individuels
    4. Consolidation ALL_LC (build_all_lc + split_axial)
    5. Jointure avec le mapping ELE → éléments des CdC absents de l'ELE
       écartés du calcul (warning, non bloquant)
    6. Identifiants RC référencés par les éléments mais non configurés dans
       rc_configs → éléments concernés écartés du calcul (warning, non
       bloquant)
    7. build_response() → Format 1 + Format 2 + métadonnées + warnings
    """
    # ── 1. Validation du JSON request ────────────────────────────────────────
    try:
        calc_request = CalculationRequest.model_validate_json(request)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Paramètres de calcul invalides : {exc}",
        ) from exc

    # ── 2. Parsing fichier ELE ───────────────────────────────────────────────
    try:
        ele_raw = (await ele_file.read()).decode("utf-8", errors="replace")
        ele_df = parse_ele_file(ele_raw)
    except ValueError as exc:
        msg = str(exc)
        detail = msg if msg.startswith("Fichier ELE") else f"Fichier ELE : {msg}"
        raise HTTPException(status_code=400, detail=detail) from exc

    # ── 3. Parsing fichiers LC ───────────────────────────────────────────────
    if not lc_files:
        raise HTTPException(status_code=400, detail="Aucun fichier de cas de charge fourni.")

    lc_dfs: dict[str, "object"] = {}
    for f in lc_files:
        lc_name = _lc_name_from_filename(f.filename)
        if lc_name in lc_dfs:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cas de charge '{lc_name}' fourni plusieurs fois "
                    f"(noms de fichiers en double une fois l'extension retirée)."
                ),
            )
        try:
            raw = (await f.read()).decode("utf-8", errors="replace")
            lc_dfs[lc_name] = parse_lc_file(raw, lc_name)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Fichier {f.filename} : {exc}",
            ) from exc

    # ── 4. Consolidation ALL_LC ───────────────────────────────────────────────
    try:
        all_lc = build_all_lc(lc_dfs)
        all_lc = split_axial(all_lc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ── 5. Jointure avec le mapping élément → RC ─────────────────────────────
    # Non bloquant : un élément présent dans les CdC mais absent de l'ELE est
    # généralement un outil de modélisation EF (élément rigide, connecteur,
    # collecteur...) sans vocation à être vérifié. On l'écarte du calcul
    # plutôt que de bloquer, et on garde une trace dans `warnings`.
    all_lc = all_lc.merge(ele_df, on="element_id", how="left")
    extra_warnings: list[str] = []
    missing = all_lc[all_lc["rc_number"].isna()]
    if not missing.empty:
        missing_ids = sorted(missing["element_id"].unique().tolist())
        extra_warnings.append(
            f"{len(missing_ids)} élément(s) présent(s) dans les fichiers de "
            f"cas de charge mais absent(s) du fichier ELE — écarté(s) du "
            f"calcul : "
            f"{missing_ids[:10]}{'…' if len(missing_ids) > 10 else ''}"
        )
        all_lc = all_lc[all_lc["rc_number"].notna()].copy()
    all_lc["rc_number"] = all_lc["rc_number"].astype(str)

    # ── 6. Vérification des RC référencés ────────────────────────────────────
    # Même logique : un identifiant RC présent dans l'ELE mais non configuré
    # (élément volontairement non calculé) écarte ses éléments plutôt que
    # de bloquer tout le calcul.
    configured_rcs = {rc.rc_number for rc in calc_request.rc_configs}
    used_rcs = set(all_lc["rc_number"].unique().tolist())
    unknown_rcs = sorted(used_rcs - configured_rcs)
    if unknown_rcs:
        excluded_elements = sorted(
            all_lc.loc[all_lc["rc_number"].isin(unknown_rcs), "element_id"].unique().tolist()
        )
        extra_warnings.append(
            f"Numéro(s) RC présent(s) dans le fichier ELE mais sans "
            f"configuration correspondante dans rc_configs — éléments "
            f"concernés écartés du calcul : RC {unknown_rcs}, éléments "
            f"{excluded_elements[:10]}{'…' if len(excluded_elements) > 10 else ''}"
        )
        all_lc = all_lc[all_lc["rc_number"].isin(configured_rcs)].copy()

    # ── 6bis. Éléments configurés mais sans aucune donnée de charge ──────────
    # Un élément déclaré dans l'ELE avec un RC configuré est censé être
    # vérifié. S'il n'apparaît dans aucun fichier LC, ce n'est pas un choix
    # volontaire (contrairement aux étapes 5-6) mais probablement un oubli
    # d'export CdC ou une erreur de numérotation — signalé, non bloquant.
    calculated_ele_ids = set(
        ele_df.loc[ele_df["rc_number"].isin(configured_rcs), "element_id"]
    )
    loaded_ele_ids = set(all_lc["element_id"].unique().tolist())
    never_loaded = sorted(calculated_ele_ids - loaded_ele_ids)
    if never_loaded:
        extra_warnings.append(
            f"{len(never_loaded)} élément(s) déclaré(s) dans le fichier ELE "
            f"avec un RC configuré, mais absent(s) de tous les fichiers de "
            f"cas de charge — aucune vérification effectuée faute de "
            f"données (vérifier l'export CdC ou la numérotation) : "
            f"{never_loaded[:10]}{'…' if len(never_loaded) > 10 else ''}"
        )

    # ── 6ter. Éléments couverts par certains CdC seulement (pas tous) ────────
    # Un élément configuré présent dans au moins un LC mais absent d'un ou
    # plusieurs autres n'est vérifié que sur les CdC où il a des données :
    # l'enveloppe peut être incomplète si le CdC manquant aurait été
    # dimensionnant pour lui — signalé, non bloquant (peut être volontaire
    # si les CdC sont scindés par zone de structure).
    all_lc_names = set(lc_dfs.keys())
    if len(all_lc_names) > 1:
        lc_coverage = all_lc.groupby("element_id")["lc_name"].agg(set)
        partial = sorted(
            eid for eid, lcs in lc_coverage.items()
            if eid in calculated_ele_ids and lcs != all_lc_names
        )
        if partial:
            extra_warnings.append(
                f"{len(partial)} élément(s) avec RC configuré présent(s) "
                f"dans certains fichiers de cas de charge seulement (pas "
                f"tous) — vérifiés uniquement sur les CdC où ils ont des "
                f"données, l'enveloppe peut être incomplète : "
                f"{partial[:10]}{'…' if len(partial) > 10 else ''}"
            )

    # ── 7. Calcul ──────────────────────────────────────────────────────────────
    materials = {m.material_number: m for m in calc_request.material_configs}
    try:
        return build_response(calc_request.rc_configs, materials, all_lc, extra_warnings=extra_warnings)
    except KeyError as exc:
        # Désignation de section introuvable au catalogue (get_section)
        raise HTTPException(status_code=400, detail=f"Erreur de catalogue : {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Erreur de calcul : {exc}") from exc
    except Exception as exc:  # pragma: no cover — filet de sécurité
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne inattendue lors du calcul : {exc}",
        ) from exc
    
