# Guide de déploiement — Calcul HUOX Web

Backend FastAPI → **Render.com**  
Frontend React/Vite → **Netlify**

---

## Prérequis

- Compte [Render.com](https://render.com) (tier gratuit suffisant)
- Compte [Netlify](https://app.netlify.com) (tier gratuit suffisant)
- Dépôt Git public ou privé (GitHub / GitLab / Bitbucket)
- Les fichiers `render.yaml` (racine) et `frontend/netlify.toml` sont déjà présents

---

## Étape 1 — Pousser le dépôt

```bash
git init                          # si pas encore initialisé
git add .
git commit -m "Initial commit"
git remote add origin <url-repo>
git push -u origin main
```

> **Note :** Les CSV de catalogue (`backend/data/*.csv`) sont versionnés — ils seront
> déployés automatiquement avec le reste du code. Ne pas les ignorer.

---

## Étape 2 — Déployer le backend sur Render

### 2a. Créer le service

1. Render dashboard → **New** → **Web Service**
2. Connecter le dépôt Git
3. Render détecte automatiquement `render.yaml` à la racine → cliquer **Apply**

Si Render ne détecte pas `render.yaml`, configurer manuellement :

| Champ            | Valeur                                              |
|------------------|-----------------------------------------------------|
| Name             | `calcul-huox-api`                                   |
| Runtime          | Python 3                                            |
| Root Directory   | `backend`                                           |
| Build Command    | `pip install -r requirements.txt`                   |
| Start Command    | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

### 2b. Variables d'environnement Render

Dans **Environment** du service, ajouter :

| Clé             | Valeur                                       |
|-----------------|----------------------------------------------|
| `PYTHON_VERSION`| `3.11.0`                                     |
| `CORS_ORIGINS`  | `https://<nom-site>.netlify.app`             |

> L'URL Netlify n'est connue qu'après l'étape 3. Laisser `CORS_ORIGINS` vide pour
> l'instant ou mettre une valeur temporaire ; à mettre à jour après l'étape 3.

### 2c. Lancer le premier déploiement

Cliquer **Deploy** → patienter ~2 min.

Une fois terminé, noter l'URL publique du service :
```
https://calcul-huox-api.onrender.com   ← exemple
```

Vérifier que le backend répond :
```
https://calcul-huox-api.onrender.com/health
→ {"status": "ok"}
```

---

## Étape 3 — Déployer le frontend sur Netlify

### 3a. Créer le site

1. Netlify dashboard → **Add new site** → **Import an existing project**
2. Connecter le même dépôt Git
3. Configurer le build :

| Champ              | Valeur     |
|--------------------|------------|
| Base directory     | `frontend` |
| Build command      | `npm run build` |
| Publish directory  | `dist`     |

> `netlify.toml` dans `frontend/` prend le dessus une fois le Base directory configuré.

### 3b. Variables d'environnement Netlify

**Site configuration → Environment variables → Add a variable :**

| Clé              | Valeur                                        |
|------------------|-----------------------------------------------|
| `VITE_API_URL`   | `https://calcul-huox-api.onrender.com`        |

Remplacer par l'URL réelle obtenue à l'étape 2c.

### 3c. Lancer le déploiement

**Deploys → Trigger deploy → Deploy site** → patienter ~1 min.

L'URL du site sera du type :
```
https://calcul-huox.netlify.app   ← exemple
```

---

## Étape 4 — Finaliser la configuration CORS

Mettre à jour `CORS_ORIGINS` dans Render avec l'URL Netlify définitive :

```
CORS_ORIGINS = https://calcul-huox.netlify.app
```

Si un domaine custom est ajouté plus tard, séparer les origines par une virgule :
```
CORS_ORIGINS = https://calcul-huox.netlify.app,https://calcul-huox.example.com
```

Render redéploie automatiquement après modification d'une variable d'environnement.

---

## Étape 5 — Vérification end-to-end

1. Ouvrir l'URL Netlify dans le navigateur
2. Ajouter un RC, un matériau, charger les fichiers Ansys
3. Cliquer **Lancer le calcul**

> ⚠ **Cold start Render (tier gratuit) :** le service se met en pause après
> 15 minutes d'inactivité. Le premier calcul après une longue période d'inactivité
> peut prendre **30 à 60 secondes** — c'est normal. Un message d'attente est affiché
> dans l'interface.

---

## Mises à jour

Chaque `git push` sur la branche principale déclenche automatiquement :
- un redéploiement Render (backend)
- un redéploiement Netlify (frontend)

---

## Diagnostics courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| `/health` ne répond pas | Service Render en pause | Attendre le cold start (30–60 s) |
| Erreur CORS dans la console | `CORS_ORIGINS` incorrect | Vérifier l'URL Netlify dans les env vars Render |
| `VITE_API_URL is not defined` | Variable Netlify absente | Ajouter `VITE_API_URL` dans Netlify env vars |
| Calcul retourne 500 | CSV catalogue manquant | Vérifier que `backend/data/*.csv` est bien poussé dans Git |
| Build Netlify échoue | Node version incompatible | `NODE_VERSION=20` dans netlify.toml ou env vars Netlify |
| Build Render échoue | Python version incompatible | Vérifier `backend/.python-version` = `3.11` |
