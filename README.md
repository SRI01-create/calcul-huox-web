# Calcul HUOX — Web

Post-traitement EC3 pour éléments linéaires en acier issus de calculs EF Ansys.  
Vérification des exigences de résistance et de stabilité selon **NF EN 1993-1-1** et **NF EN 1993-1-4**.

---

## Architecture

```
calcul-huox-web/
├── backend/          Python · FastAPI · Pandas/NumPy
│   ├── app/
│   │   ├── ec3/      Moteur de calcul EC3 (phases 5–14)
│   │   └── engines/  Orchestrateurs H / U / O / X (phases 15–16)
│   ├── data/         Catalogues de sections CSV (générés en phase 1)
│   └── scripts/      Scripts one-shot (extraction catalogues)
└── frontend/         React · Vite · Tailwind CSS
    └── src/
        └── components/
```

**Déploiement :**
- Backend  → [Render.com](https://render.com) (tier gratuit)
- Frontend → [Netlify](https://netlify.com)

## Déploiement

Voir [`DEPLOY.md`](./DEPLOY.md) pour le guide complet Render + Netlify.

---

## Installation locale

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # Adapter si nécessaire
uvicorn app.main:app --reload    # http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local       # Adapter si nécessaire
npm run dev                      # http://localhost:5173
```


> Les catalogues CSV (`backend/data/*.csv`) sont versionnés dans le dépôt — aucune génération manuelle n'est nécessaire.  
> Pour les régénérer depuis l'xlsm source : `python backend/scripts/extract_catalogues.py`

---

## Vérifications EC3 couvertes

| Catégorie | Détail |
|---|---|
| Classe de section | Classes 1, 2, 3 (classe 4 : non prise en charge) |
| Résistance section | Traction · Compression · Flexion · Cisaillement · Torsion |
| Combinées section | Cisaillement+Torsion · Flexion+Cisaillement+Torsion+N |
| Flambement | Par flexion (y-y, z-z) · Par torsion · Flexion-torsion |
| Déversement | 6 configurations + Mcr manuel · Sections H et U |
| Interaction stabilité | kyy / kyz / kzy / kzz (Annexe A) |
| Aciers inoxydables | EN 1993-1-4 (ky, kz, kLT) |

---

## Références normatives

NF EN 1993-1-1 · EN 1993-1-1 NA · NF EN 1993-1-4 · NF EN 1993-1-4 NA  
CAL-ELE 1-2000 · SN001a-FR-EU · SN003b-FR-EU · SN007b-FR-EU  
Revue Construction Métallique n°2-2016 · Catalogue ArcelorMittal

---

*Développé par Sem Riazi — Propriété exclusive, tous droits réservés.*
