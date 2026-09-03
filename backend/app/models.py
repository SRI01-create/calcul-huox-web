"""
Phase 3 — Modèles de données Pydantic (validation des entrées et sorties API).

Hiérarchie
----------
Entrées :
    RCConfig          → paramètres d'un numéro RC (feuille "1" côté RC)
    MaterialConfig    → propriétés d'un matériau (feuille "1" côté matériau)
    CalculationRequest → requête complète envoyée à POST /api/calculate

Sorties :
    AllRatios         → les 14 ratios EC3 d'une ligne élément×CdC
    ElementLCResult   → une ligne résultat complète (Format 2)
    RCSummary         → synthèse par RC (Format 1)
    CalculationResponse → réponse complète de l'API

Unités attendues dans les fichiers Ansys importés
-------------------------------------------------
    Efforts tranchants Vy, Vz  : N
    Effort normal Fx            : N  (positif = traction)
    Moment de torsion Mx        : N.m
    Moments fléchissants My, Mz : N.m

Unités des propriétés de section (depuis catalogue)
----------------------------------------------------
    h, b, tw, tf, t, r, d       : mm
    A, Av_y, Av_z               : m²
    Iy, Iz, It                  : m⁴
    Wel_y/z, Wpl_y/z            : m³
    IW                          : m⁶
    Sw (H) / Sw_w (U)           : m⁴
    ys, ym (U)                  : mm

Unités des paramètres matériau
------------------------------
    fy, fu, E, G                : MPa  (= N/mm²)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ═══════════════════════════════════════════════════════════════════════════════
# ÉNUMÉRATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class SectionType(str, Enum):
    H = "H"   # Ouverte bi-symétrique  (I, H : IPE, HEA, HEB, PRS H…)
    U = "U"   # Ouverte mono-symétrique (U, cornières : UPE, UPN, L…)
    O = "O"   # Fermée creuse           (Tca, Tre, Tci)
    X = "X"   # Pleine                  (Pca, Pre, Pci)


class SteelType(str, Enum):
    CARBON    = "carbone"
    STAINLESS = "inox"


class FabricationType(str, Enum):
    """L = laminé ou formé à froid · S = PRS soudé (influence λLT,0 et courbe déversement)."""
    LAMINATED = "L"
    WELDED    = "S"


class HoleType(str, Enum):
    """P = pleine · T = trouée cat. A/B · C = trouée cat. C."""
    FULL     = "P"
    HOLED_AB = "T"
    HOLED_C  = "C"


class BucklingCurve(str, Enum):
    A0 = "a0"
    A  = "a"
    B  = "b"
    C  = "c"
    D  = "d"


# ═══════════════════════════════════════════════════════════════════════════════
# MODÈLES D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════════════

class RCConfig(BaseModel):
    """
    Paramètres d'un numéro RC — correspond à une ligne de la feuille "1" côté RC.
    """
    model_config = ConfigDict(use_enum_values=True)

    # ── Identification ───────────────────────────────────────────────────────
    rc_number: str = Field(
        ..., min_length=1, max_length=16,
        description=(
            "Identifiant du RC — texte libre court (16 caractères max), sans "
            "espace ni tabulation. Par défaut, numérotation automatique "
            "('1', '2', '3'…) ; l'utilisateur peut le remplacer par tout "
            "identifiant de son choix (ex. 'Poutre-1'), à condition qu'il "
            "corresponde exactement (comparaison texte stricte, sans "
            "normalisation numérique) au token de la 2ᵉ colonne du fichier "
            "ELE. Contrainte de format (pas d'espace) commune au fichier ELE "
            "et à la plupart des logiciels EF."
        ),
    )
    section_type:   SectionType = Field(..., description="Type de section : H | U | O | X")
    designation:    str         = Field(..., min_length=1, description="Désignation exacte du catalogue")
    material_number: int        = Field(..., ge=1, description="Référence vers MaterialConfig.material_number")
    manual_section_class: Optional[Literal["1", "2", "3", "4"]] = Field(
        None,
        description=(
            "Classe de section imposée par l'utilisateur (1 à 4), en remplacement "
            "de la classe auto-calculée de façon conservative. Aucune restriction "
            "n'est appliquée (outil destiné à des ingénieurs responsables de leurs "
            "calculs) ; un warning informatif est ajouté à la réponse si la classe "
            "forcée diffère de la classe auto-calculée. None = pas de classe forcée."
        ),
    )

    # ── Flambement par flexion ───────────────────────────────────────────────
    L:   float = Field(..., gt=0, description="Longueur de barre (m)")
    cry: float = Field(1.0, gt=0, description="Coeff. longueur flambement axe y-y → Lcr,y = cry × L")
    crz: float = Field(1.0, gt=0, description="Coeff. longueur flambement axe z-z → Lcr,z = crz × L")
    buckling_curve_y: BucklingCurve = Field(BucklingCurve.B, description="Courbe de flambement axe y-y")
    buckling_curve_z: BucklingCurve = Field(BucklingCurve.C, description="Courbe de flambement axe z-z")

    # ── Guide de choix des courbes de flambement (Phase 29) ──────────────────
    # Purement indicatif : ces 4 champs n'alimentent QUE la suggestion
    # affichée à l'utilisateur (endpoint /api/buckling-curve/...) — aucun
    # moteur de calcul (engine_H/U/O/X.py) ne les lit jamais. Les courbes
    # réellement utilisées restent buckling_curve_y / buckling_curve_z
    # ci-dessus, renseignées indépendamment (à la main ou via la suggestion).
    bc_steel_family: Optional[Literal["s235_s420", "s460", "inox"]] = Field(
        None,
        description=(
            "Nuance (regroupée) utilisée par le guide de choix des courbes de "
            "flambement — H et O uniquement. Purement indicatif."
        ),
    )
    bc_u_shape: Optional[Literal["profile", "corniere"]] = Field(
        None,
        description=(
            "Forme du profil, utilisée par le guide de choix des courbes de "
            "flambement — U uniquement. Choix explicite de l'utilisateur, "
            "indépendant de la détection automatique de cornière (is_angle) "
            "utilisée par ailleurs dans le calcul. Purement indicatif."
        ),
    )
    bc_u_material: Optional[Literal["carbone", "inox", "inox_forme_a_froid"]] = Field(
        None,
        description=(
            "Matériau utilisé par le guide de choix des courbes de flambement — "
            "U uniquement. Purement indicatif."
        ),
    )
    bc_o_shape: Optional[Literal[
        "creuse_chaud", "creuse_froid", "caisson_soude", "caisson_soude_a_sup_05tf",
    ]] = Field(
        None,
        description=(
            "Forme de la section creuse utilisée par le guide de choix des "
            "courbes de flambement — O uniquement, nuances carbone "
            "(s235_s420/s460) seulement. Purement indicatif."
        ),
    )

    # ── Flambement par torsion (H et U uniquement) ───────────────────────────
    crT: float = Field(1.0, gt=0, description="Coeff. longueur flambement par torsion → Lcr,T = crT × L")

    # ── Déversement (H et U uniquement) ─────────────────────────────────────
    Lm: float = Field(..., gt=0, description="Longueur entre maintiens latéraux (m)")
    ltb_config: str = Field(
        "3",
        description=(
            "Configuration de déversement : '1' à '6' (tableau EC3 simplifié) "
            "ou valeur numérique du Mcr en N.m (ex. '12500.0' pour Mcr manuel)"
        ),
    )
    fabrication: FabricationType = Field(
        FabricationType.LAMINATED,
        description="L = laminé/formé à froid · S = PRS soudé (influence λLT,0 et courbe LTB)",
    )
    zG: float = Field(
        0.0,
        description=(
            "Distance entre le point d'application de la charge et le centre de "
            "cisaillement (mm). Positif si la charge est au-dessus du CDG (déstabilisant)."
        ),
    )

    # ── Trous ────────────────────────────────────────────────────────────────
    PTC: HoleType = Field(HoleType.FULL, description="P = pleine · T = trouée A/B · C = trouée C")
    A_trou:  Optional[float] = Field(None, ge=0, description="Aire totale des trous (m²)")
    Af_trou: Optional[float] = Field(None, ge=0, description="Aire des trous dans la semelle (m²)")
    kr: float = Field(
        1.0, gt=0, le=1.0,
        description="Coefficient de participation à la traction (inox trouée, typiquement 0.9 ou 0.7)",
    )

    # ── Validateurs ──────────────────────────────────────────────────────────
    @field_validator("rc_number")
    @classmethod
    def validate_rc_number(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("rc_number ne peut pas être vide.")
        if any(c.isspace() for c in v):
            raise ValueError(
                f"rc_number '{v}' contient un espace ou une tabulation, ce "
                "qui est incompatible avec le format du fichier ELE (jetons "
                "séparés par des espaces) — utiliser un caractère comme '-' "
                "ou '_' à la place."
            )
        return v

    @field_validator("ltb_config")
    @classmethod
    def validate_ltb_config(cls, v: str) -> str:
        if v.strip() in ("1", "2", "3", "4", "5", "6"):
            return v.strip()
        try:
            val = float(v)
            if val <= 0:
                raise ValueError
            return str(val)
        except (ValueError, TypeError):
            raise ValueError(
                "ltb_config doit être '1'–'6' (configuration) "
                "ou une valeur numérique positive de Mcr en N.m"
            )

    @model_validator(mode="after")
    def validate_holes(self) -> "RCConfig":
        if self.PTC in ("T", "C"):
            if self.A_trou is None or self.A_trou == 0:
                raise ValueError("A_trou requis et non nul pour PTC = 'T' ou 'C'")
        return self


class MaterialConfig(BaseModel):
    """
    Propriétés d'un matériau — correspond à une ligne de la feuille "1" côté matériau.
    """
    model_config = ConfigDict(use_enum_values=True)

    material_number: int        = Field(..., ge=1)
    designation:     str        = Field(..., min_length=1, description="Ex. '1.0038' pour S235")
    fy:  float = Field(..., gt=0, description="Limite d'élasticité (MPa)")
    fu:  float = Field(..., gt=0, description="Résistance à la traction (MPa)")
    E:   float = Field(..., gt=0, description="Module de Young (MPa, typiquement 210 000)")
    G:   float = Field(..., gt=0, description="Module de cisaillement (MPa, typiquement 80 770)")
    steel_type: SteelType = Field(SteelType.CARBON, description="carbone | inox")

    @model_validator(mode="after")
    def validate_fy_fu(self) -> "MaterialConfig":
        if self.fy >= self.fu:
            raise ValueError(f"fy ({self.fy} MPa) doit être strictement inférieur à fu ({self.fu} MPa)")
        return self


class CalculationRequest(BaseModel):
    """
    Requête de calcul envoyée à POST /api/calculate (corps JSON).
    Les fichiers ELE et LC sont uploadés séparément en multipart/form-data.
    """
    rc_configs:       list[RCConfig]       = Field(..., min_length=1)
    material_configs: list[MaterialConfig] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_material_refs(self) -> "CalculationRequest":
        """Vérifie que chaque RC référence un numéro de matériau existant."""
        mat_numbers = {m.material_number for m in self.material_configs}
        for rc in self.rc_configs:
            if rc.material_number not in mat_numbers:
                raise ValueError(
                    f"RC {rc.rc_number} : matériau n°{rc.material_number} introuvable "
                    f"dans material_configs (disponibles : {sorted(mat_numbers)})"
                )
        return self


# ═══════════════════════════════════════════════════════════════════════════════
# MODÈLES DE RÉSULTATS
# ═══════════════════════════════════════════════════════════════════════════════

class AllRatios(BaseModel):
    """
    Les 14 ratios de vérification EC3 pour une ligne élément × cas de charge.
    None = vérification non applicable pour ce type de section.
    """
    # ── Résistance de la section transversale ──────────────────────────────
    ratio_N:    Optional[float] = None  # rN,Ed/Rd      — traction ou compression pure
    ratio_Vy:   Optional[float] = None  # rV,y,Ed/Rd    — cisaillement pur y
    ratio_Vz:   Optional[float] = None  # rV,z,Ed/Rd    — cisaillement pur z
    ratio_T:    Optional[float] = None  # rT,Ed/Rd      — torsion pure
    ratio_cy:   Optional[float] = None  # rc,y,Ed/Rd    — flexion pure My
    ratio_cz:   Optional[float] = None  # rc,z,Ed/Rd    — flexion pure Mz
    ratio_VyT:  Optional[float] = None  # rV,y,T,Ed/Rd  — cisaillement y avec torsion
    ratio_VzT:  Optional[float] = None  # rV,z,T,Ed/Rd  — cisaillement z avec torsion
    ratio_cVN:  Optional[float] = None  # rc,V,N,Ed/Rd  — combinée N + V + M section

    # ── Instabilité ───────────────────────────────────────────────────────
    ratio_Nb_F:  Optional[float] = None  # rN,Ed/b,F   — flambement par flexion
    ratio_Nb_TF: Optional[float] = None  # rN,Ed/b,TF  — flambement torsion-flexion (H, U)
    ratio_Mb:    Optional[float] = None  # rM,Ed/b     — déversement (H, U)
    ratio_MNy_b: Optional[float] = None  # rM,N,y,Ed/b — combinée stabilité axe y
    ratio_MNz_b: Optional[float] = None  # rM,N,z,Ed/b — combinée stabilité axe z

    @property
    def max_ratio(self) -> Optional[float]:
        """Ratio maximal sur toutes les vérifications applicables."""
        vals = [v for v in self.__dict__.values() if v is not None]
        return max(vals) if vals else None


class ElementLCResult(BaseModel):
    """
    Résultat complet pour une combinaison élément × cas de charge.
    Correspond au Format 2 (une ligne du tableau détaillé).
    """
    lc_name:      str
    element_id:   int
    rc_number:    str
    section_type: str
    designation:  str
    section_class: str   # "1", "2", "3" ou "4" (non vérifié)
    is_welded:     bool = False   # section soudée (PRS) — Phase 31, pour flag Format 2
    is_angle:      bool = False   # cornière (U uniquement) — Phase 30, pour badge Format 2
    is_circular:   bool = False   # section circulaire (O/X uniquement) — Phase 30, pour badge Format 2

    # Efforts internes (N et N.m)
    NEd_t: float = 0.0   # Traction (N)
    NEd_c: float = 0.0   # Compression (N)
    Vy_Ed: float = 0.0   # Tranchant y (N)
    Vz_Ed: float = 0.0   # Tranchant z (N)
    TEd:   float = 0.0   # Torsion (N.m)
    My_Ed: float = 0.0   # Moment y (N.m)
    Mz_Ed: float = 0.0   # Moment z (N.m)

    ratios: AllRatios
    max_ratio: Optional[float] = None
    shear_buckling_ok: bool = True   # False si h/tw > 72ε (avertissement)


class RCSummary(BaseModel):
    """
    Synthèse par numéro RC — correspond au Format 1.
    Contient les propriétés de la section, les résistances calculées,
    les efforts internes maximaux et les ratios maximaux sur tous les éléments et CdC.
    """
    rc_number:    str
    section_type: str
    designation:  str
    section_class: str
    section_class_auto: str  # classe auto-calculée (conservative) — identique à
                              # section_class sauf si manual_section_class est renseigné
    is_welded:    bool
    is_angle:     bool = False   # cornière (U uniquement, sinon False) — Phase 30
    is_circular:  bool = False   # section circulaire (O/X uniquement, sinon False) — Phase 30

    # ── Propriétés géométriques principales ──────────────────────────────
    h:  Optional[float] = None   # mm
    b:  Optional[float] = None   # mm
    tw: Optional[float] = None   # mm (H, U)
    tf: Optional[float] = None   # mm (H, U)
    t:  Optional[float] = None   # mm (O)
    A:  Optional[float] = None   # m²

    # ── Matériau ─────────────────────────────────────────────────────────
    material_designation: str    = ""
    fy:  Optional[float] = None  # MPa
    fu:  Optional[float] = None  # MPa
    E:   Optional[float] = None  # MPa
    G:   Optional[float] = None  # MPa
    steel_type: str = "carbone"
    gamma_M0: float = 1.0
    gamma_M1: float = 1.0
    gamma_M2: float = 1.25
    epsilon:  Optional[float] = None

    # ── Résistances calculées (N ou N.m) ─────────────────────────────────
    Nt_Rd:    Optional[float] = None
    Nc_Rd:    Optional[float] = None
    My_c_Rd:  Optional[float] = None
    Mz_c_Rd:  Optional[float] = None
    Vy_pl_Rd: Optional[float] = None
    Vz_pl_Rd: Optional[float] = None
    Mb_Rd:    Optional[float] = None   # N.m (H, U)
    Nb_y_Rd:  Optional[float] = None
    Nb_z_Rd:  Optional[float] = None
    Nb_TF_Rd: Optional[float] = None   # H, U

    # ── Paramètres de stabilité ───────────────────────────────────────────
    lambda_y:   Optional[float] = None
    lambda_z:   Optional[float] = None
    lambda_LT:  Optional[float] = None
    lambda_LT0: Optional[float] = None
    Mcr:        Optional[float] = None  # N.m

    # ── Efforts internes maximaux ─────────────────────────────────────────
    NEd_t_max: float = 0.0
    NEd_c_max: float = 0.0
    Vy_max:    float = 0.0
    Vz_max:    float = 0.0
    T_max:     float = 0.0
    My_max:    float = 0.0
    Mz_max:    float = 0.0

    # ── Ratios maximaux ───────────────────────────────────────────────────
    max_ratios: AllRatios
    overall_max_ratio: Optional[float] = None
    shear_buckling_warning: bool = False


class CalculationResponse(BaseModel):
    """Réponse complète de POST /api/calculate."""
    format1: list[RCSummary]        # Synthèse par RC
    format2: list[ElementLCResult]  # Détail toutes lignes
    nb_elements:    int
    nb_load_cases:  int
    nb_combinations: int             # = len(format2)
    warnings: list[str] = []         # Avertissements non bloquants
