# Document de reprise — Calcul HUOX Web

## Consignes pour Claude

Tu reprends un projet en cours. Lis ce document intégralement, puis
demande les fichiers nécessaires si l'utilisateur ne les a pas encore joints :

1. `calcul-huox-web-phase20.zip` — le code produit jusqu'ici
2. `CALCUL_HUOX_EC3_-_V16_-_np.xlsm` — le fichier Excel source  
   (nécessaire uniquement pour les phases de calcul EC3 — plus de phases EC3 restantes)

Règles de travail :
- S'arrêter après chaque phase et attendre le feu vert
- Toujours tester le code avec des valeurs numériques vérifiées
- Si tu approches de la limite de tokens, t'arrêter proprement et indiquer ce qu'il reste

---

## Le projet

**Objectif :** Transformer l'outil Excel CALCUL HUOX en site web.

**L'outil Excel** post-traite des résultats EF Ansys pour vérifier des éléments
linéaires en acier selon l'Eurocode 3 (NF EN 1993-1-1 / 1-4).

**Architecture :**
- Backend Python/FastAPI → Render.com
- Frontend React/Vite/Tailwind → Netlify
- Calcul vectorisé Pandas/NumPy
- `POST /api/calculate` reçoit config JSON + fichiers Ansys → retourne JSON résultats

---

## État d'avancement

| Phase | Contenu | Fichier | État |
|-------|---------|---------|------|
| 0 | Structure projet | — | ✅ |
| 1 | Extraction catalogues → CSV | `scripts/extract_catalogues.py` | ✅ |
| 2 | Module catalogue (lookup) | `app/catalogue.py` | ✅ |
| 3 | Modèles Pydantic | `app/models.py` | ✅ |
| 4 | Parseurs fichiers Ansys | `app/parsers.py` | ✅ |
| 5 | Utilitaires EC3 communs (ε, γM, χ…) | `app/ec3/utils.py` | ✅ |
| 6 | Classification de section | `app/ec3/classification.py` | ✅ |
| 7 | Résistances pures (N, M, V) | `app/ec3/section_pure.py` | ✅ |
| 8 | Torsion + cisaillement réduit | `app/ec3/torsion.py` | ✅ |
| 9 | Résistances combinées section | `app/ec3/section_combined.py` | ✅ |
| 10 | Flambement par flexion | `app/ec3/buckling_flexural.py` | ✅ |
| 11 | Flambement torsion/flexion-torsion | `app/ec3/buckling_torsional.py` | ✅ |
| 12 | Déversement — Mcr | `app/ec3/ltb_mcr.py` | ✅ |
| 13 | Déversement — χLT et Mb,Rd | `app/ec3/ltb_resistance.py` | ✅ |
| 14 | Facteurs d'interaction kyy/kyz/kzy/kzz | `app/ec3/interaction.py` | ✅ |
| 15 | Moteur de calcul H (vectorisé) | `app/engines/engine_H.py` | ✅ |
| 16 | Moteurs U, O, X + dispatcher | `app/engines/engine_*.py` + `dispatch.py` | ✅ |
| 17 | Compilation résultats (Format 1 + 2) | `app/results.py` | ✅ |
| 18 | API FastAPI (endpoints) | `app/main.py` | ✅ |
| 19 | Frontend — setup + état global | `src/store.js`, `src/api.js` | ✅ |
| 20 | Frontend — formulaire RC + matériaux | `src/components/RCRow.jsx`, `RCForm.jsx`, `MaterialRow.jsx`, `MaterialForm.jsx` | ✅ |
| **21** | **Frontend — import fichiers + calcul** | **`src/components/FileUpload.jsx`, `CalculateButton.jsx`** | **✅ DÉJÀ FAIT** |
| 22 | Frontend — résultats Format 1 | `src/components/ResultsFormat1.jsx` | ⬜ stub |
| 23 | Frontend — résultats Format 2 | `src/components/ResultsFormat2.jsx` | ⬜ stub |
| 24 | Déploiement Render + Netlify | configs | ⬜ |
| 25 | Tests validation (11 cas) | `tests/test_validation.py` | ⬜ stub |

**→ Prochaine phase : Phase 22 — Résultats Format 1**

---

## Attention : Phase 21 déjà complète

`FileUpload.jsx` et `CalculateButton.jsx` ont été écrits à la fin de
la Phase 20 et sont déjà complets dans le zip. `App.jsx` les importe
et les utilise. Ne pas re-coder ces composants.

---

## Architecture du code

### Backend (`backend/`)

```
app/
├── main.py              # FastAPI : GET /health, GET /api/sections/{type},
│                        #           GET /api/sections/{type}/{designation},
│                        #           POST /api/calculate (multipart/form-data)
├── models.py            # Pydantic : RCConfig, MaterialConfig, CalculationRequest,
│                        #            AllRatios, ElementLCResult, RCSummary,
│                        #            CalculationResponse
├── catalogue.py         # Chargement CSV + get_section() + list_sections() + preload_all()
├── parsers.py           # parse_ele_file(), parse_lc_file(), build_all_lc(), split_axial()
├── results.py           # build_response() → CalculationResponse (point d'entrée API)
├── ec3/
│   ├── utils.py              # epsilon(), gamma_M(), chi_reduction(), buckling_curve_alpha()
│   ├── classification.py     # section_class_H/U/O/X(), net_areas(), can_ignore_*()
│   ├── section_pure.py       # Nt_Rd(), Nc_Rd(), Mc_Rd(), Vpl_Rd()
│   ├── torsion.py            # tau_w_H(), tau_mixed_U(), tau_bredt_O(), tau_solid_X(),
│   │                         # Vpl_T_Rd_H(), Vpl_T_Rd_UOX()
│   ├── section_combined.py   # MV_Rd(), My_N_Rd_HU/O(), MN_Rd_X(),
│   │                         # ratio_combined_H/U/O/X()
│   ├── buckling_flexural.py  # flexural_buckling(), lambda0_flexural(), ncr_euler()
│   ├── buckling_torsional.py # torsional_buckling(), ncr_torsional(), ncr_flex_torsional()
│   ├── ltb_mcr.py            # compute_Mcr(), LTB_CONFIGS (table Annexe F)
│   ├── ltb_resistance.py     # ltb_resistance(), chi_LT(), alpha_LT_H/U()
│   └── interaction.py        # interaction_factors() → kyy/kyz/kzy/kzz, CW, CX
└── engines/
    ├── common.py        # compute_stability(), helpers ratio_*, overall_max()
    ├── engine_H.py      # run_H() + precompute()
    ├── engine_U.py      # run_U() + precompute()
    ├── engine_O.py      # run_O() + precompute()
    ├── engine_X.py      # run_X() + precompute()
    └── dispatch.py      # run_rc(), run_all(), precompute_rc()
data/
    catalogue_H.csv      # Profilés I/H (IPE, HEA, HEB, PRS…)
    catalogue_U.csv      # U et cornières (UPN, UPE, L)
    catalogue_O.csv      # Tubes creux (Tca, Tre, Tci)
    catalogue_X.csv      # Sections pleines (Pca, Pre, Pci)
```

### Frontend (`frontend/src/`)

```
api.js             # Axios client → fetchSections(), fetchSectionProperties(), runCalculation()
store.js           # Zustand + localStorage persist →
│                  #   materials[], rcConfigs[], eleFile, lcFiles[],
│                  #   result, error, isCalculating
│                  #   + actions : addMaterial/RC, updateMaterial/RC, removeMaterial/RC
│                  #   + buildPayload(), getValidationErrors(), calculate()
App.jsx            # Shell : header + nav 3 étapes + main + footer
components/
├── MaterialRow.jsx    # ✅ Carte d'édition d'un matériau (préréglages S235/S355/inox…)
├── MaterialForm.jsx   # ✅ Liste des matériaux + bouton "Ajouter"
├── RCRow.jsx          # ✅ Carte RC avec SectionPicker, groupes flambement/LTB/trous
├── RCForm.jsx         # ✅ Liste des RC + bouton "Ajouter"
├── FileUpload.jsx     # ✅ Zones drag-and-drop ELE + LC (Phase 21 déjà fait)
├── CalculateButton.jsx # ✅ Validation locale + spinner + erreurs API (Phase 21 déjà fait)
├── ResultsFormat1.jsx # ⬜ Tableau synthèse par RC (Phase 22)
├── ResultsFormat2.jsx # ⬜ Tableau détaillé par élément×CdC (Phase 23)
└── RCCard.jsx         # stub non utilisé
hooks/
└── useCalculation.js  # stub (non requis : logique dans store.calculate())
```

---

## Modèles de données clés

### `AllRatios` (14 ratios)
```
ratio_N      # NEd/Nt,Rd ou NEd/Nc,Rd
ratio_Vy     # Vy/Vpl,y
ratio_Vz     # Vz/Vpl,z
ratio_T      # τ/τ_Rd  (None pour cornière avec TEd≠0)
ratio_cy     # My/My,c,Rd
ratio_cz     # Mz/Mz,c,Rd
ratio_VyT    # Vy/Vy,pl,T,Rd
ratio_VzT    # Vz/Vz,pl,T,Rd
ratio_cVN    # combinée N+V+M section
ratio_Nb_F   # NEd/min(Nb,y, Nb,z)  flambement flexion
ratio_Nb_TF  # NEd/Nb,TF  torsion-flexion (U uniquement ; None pour H/O/X)
ratio_Mb     # My/Mb,Rd  déversement (H et U ; None pour O/X)
ratio_MNy_b  # CW §6.3.3 éq. 6.61
ratio_MNz_b  # CX §6.3.3 éq. 6.62
```
`None` = vérification hors portée pour ce type/classe. Classe 4 → presque tout à None.

### `CalculationResponse` (réponse API)
```json
{
  "format1": [RCSummary],       // 1 ligne par RC
  "format2": [ElementLCResult], // 1 ligne par élément × CdC, trié (rc, elem, lc)
  "nb_elements": int,
  "nb_load_cases": int,
  "nb_combinations": int,       // = len(format2)
  "warnings": ["string"]        // classe 4, voilement âme…
}
```

### `RCSummary` (Format 1 — champs principaux)
```
rc_number, section_type, designation, section_class, is_welded
h, b, tw, tf, t, A  [géométrie principale, mm et m²]
material_designation, fy, fu, E, G, steel_type, gamma_M0, gamma_M1, epsilon
Nt_Rd, Nc_Rd, My_c_Rd, Mz_c_Rd, Vy_pl_Rd, Vz_pl_Rd  [N et N.m]
Mb_Rd, Nb_y_Rd, Nb_z_Rd, Nb_TF_Rd  [N et N.m]
lambda_y, lambda_z, lambda_LT, lambda_LT0, Mcr  [adim. et N.m]
NEd_t_max, NEd_c_max, Vy_max, Vz_max, T_max, My_max, Mz_max  [N et N.m]
max_ratios: AllRatios  [max sur tous les éléments/CdC du RC]
overall_max_ratio: float | null
shear_buckling_warning: bool
```

---

## Points techniques importants

### Couleurs sémantiques Tailwind (tailwind.config.js)
```js
colors: {
  ratio: {
    ok:      '#16a34a', // vert   < 0.5
    warning: '#d97706', // orange 0.5 – 0.9
    danger:  '#dc2626', // rouge  0.9 – 1.0
    over:    '#7f1d1d', // rouge foncé > 1.0
  }
}
```
Utiliser `text-ratio-ok`, `bg-ratio-warning`, etc. dans les tableaux de résultats.

### Proxy Vite (développement)
`vite.config.js` proxyfie `/api` vers `http://localhost:8000`. En production,
`VITE_API_URL=https://<service>.onrender.com` est défini dans le `.env` Netlify.

### Persistance du store
`materials` et `rcConfigs` sont persistés dans `localStorage` (clé `calcul-huox-config`).
Les `File` (eleFile, lcFiles) et les résultats ne sont PAS persistés.

### Formats des fichiers Ansys parsés
**ELE :** une ligne par élément → `element_id  rc_number`

**LC :** une ligne par élément, 13 tokens :
```
element_id  Fx_max  Fx_min  Fy_max  Fy_min  Fz_max  Fz_min  Mx_max  Mx_min  My_max  My_min  Mz_max  Mz_min
```
`split_axial()` sépare Fx en `NEd_t` (max positif = traction) et `NEd_c` (max de |valeur négative| = compression).

### Cmy = Cmz = CmLT = 1.0 (hardcodé)
Ces facteurs de moment uniforme équivalent sont hardcodés à 1.0 (conservatoire).
Ils pourraient être ajoutés en champs RCConfig dans une version future.

---

## Ce qui reste à faire

### Phase 22 — `ResultsFormat1.jsx`
Tableau synthèse par RC (une ligne par RC).

Colonnes suggérées :
- N° RC | Section | Classe | Matériau | fy (MPa)
- Section : A, h, b  
- Résistances : Nt,Rd / Nc,Rd (kN) | My,c,Rd (kN·m) | Mb,Rd (kN·m) | Nb,min (kN)
- Élancements : λy | λz | λ̄LT | Mcr (kN·m)
- Efforts max : NEd,c (kN) | My (kN·m)
- **Ratios max** avec code couleur (ratio-ok/warning/danger/over)
- Avertissements (classe 4, voilement)

Données dans `store.result.format1` (liste de `RCSummary`).

### Phase 23 — `ResultsFormat2.jsx`
Tableau détaillé par élément × CdC, potentiellement très long (filtrable).

Colonnes suggérées :
- RC | Elem | CdC | Classe | NEd,c (kN) | My (kN·m) | Mz (kN·m)
- Les 14 ratios : `ratio_N` | `ratio_Vy` | `ratio_Vz` | `ratio_T` | `ratio_cy` | `ratio_cz` | `ratio_VyT` | `ratio_VzT` | `ratio_cVN` | `ratio_Nb_F` | `ratio_Nb_TF` | `ratio_Mb` | `ratio_MNy_b` | `ratio_MNz_b`
- Colonne MAX (en gras)
- Code couleur sur chaque ratio

Filtres utiles : par RC, par classe de section, par seuil de ratio (ex. > 0.9).  
Données dans `store.result.format2` (liste de `ElementLCResult`).

Remarque : `None` dans un ratio = non applicable → cellule grisée (pas de valeur).

### Phase 24 — Déploiement
**Render.com (backend) :**
```yaml
# render.yaml (à créer à la racine du dépôt)
services:
  - type: web
    name: calcul-huox-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    rootDir: backend
    envVars:
      - key: CORS_ORIGINS
        value: https://calcul-huox.netlify.app
```

**Netlify (frontend) :**
```toml
# netlify.toml (à créer dans frontend/)
[build]
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```
Variable d'environnement Netlify : `VITE_API_URL=https://<nom-service>.onrender.com`

### Phase 25 — Tests de validation (11 cas)
Fichier : `backend/tests/test_validation.py`

11 cas de validation tirés du fichier Excel original. Chaque cas = une ligne
dans une des 4 feuilles H/U/O/X, avec des résultats connus.

Les cas de validation à implémenter sont basés sur les données des feuilles
Excel. Pour chaque cas, vérifier les ratios finaux (ratio_Nb_F, ratio_Mb,
ratio_MNy_b, ratio_MNz_b notamment) à 1% de tolérance.

Exemple de structure de test :
```python
def test_H_IPN120():
    # Données de la ligne 61 feuille H
    rc = RCConfig(rc_number=1, section_type="H", designation="IPN 120", ...)
    mat = MaterialConfig(material_number=1, fy=235, ...)
    df = pd.DataFrame([{"element_id":1, "rc_number":1, "lc_name":"LC1",
                        "NEd_t":0, "NEd_c":0, ..., "My":103.5, ...}])
    result = run_H(rc, mat, df)[0]
    assert abs(result.ratios.ratio_Mb - 0.013) < 0.001
```

---

## Commandes de développement

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend  
cd frontend
npm install
npm run dev          # proxy /api → localhost:8000 automatique
npm run build        # build de production

# Tests backend
cd backend
python -m pytest tests/
```
