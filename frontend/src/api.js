// Phase 19 — Client API (axios) pour le backend FastAPI.
//
// Endpoints consommés (voir backend/app/main.py, Phase 18)
// ───────────────────────────────────────────────────────────
//   GET  /api/sections/{catType}?query=...   → liste des désignations
//   GET  /api/sections/{catType}/{designation} → propriétés d'une section
//   POST /api/calculate (multipart/form-data) → CalculationResponse
//
// Configuration de l'URL de base
// ────────────────────────────────
//   - En développement : VITE_API_URL n'est pas défini, on utilise '/api'
//     (le proxy Vite redirige vers http://localhost:8000/api, cf. vite.config.js)
//   - En production : VITE_API_URL=https://<service>.onrender.com
//     → baseURL = `${VITE_API_URL}/api`

import axios from 'axios'

// `import.meta.env` est injecté par Vite ; absent dans un script Node brut
// (tests unitaires hors Vite) — repli sur un objet vide dans ce cas.
const env = import.meta.env ?? {}

const apiBase = env.VITE_API_URL ? `${env.VITE_API_URL}/api` : '/api'

export const apiClient = axios.create({ baseURL: apiBase })

/**
 * Liste les désignations disponibles dans un catalogue de sections.
 *
 * @param {'H'|'U'|'O'|'X'} catType
 * @param {string} [query] - filtre optionnel insensible à la casse (ex. "IPE")
 * @returns {Promise<{cat_type: string, count: number, designations: string[]}>}
 */
export async function fetchSections(catType, query = '') {
  const params = query ? { query } : {}
  const { data } = await apiClient.get(`/sections/${catType}`, { params })
  return data
}

/**
 * Récupère les propriétés géométriques complètes d'une section.
 *
 * @param {'H'|'U'|'O'|'X'} catType
 * @param {string} designation - désignation exacte du catalogue (ex. "IPE 200")
 * @returns {Promise<object>} propriétés (h, b, tw, tf, A, Iy, Iz, …) + flags de forme
 */
export async function fetchSectionProperties(catType, designation) {
  const { data } = await apiClient.get(
    `/sections/${catType}/${encodeURIComponent(designation)}`
  )
  return data
}

/**
 * Lance le calcul EC3 complet.
 *
 * @param {{rc_configs: object[], material_configs: object[]}} payload
 *        - voir store.js `buildPayload()` pour la construction et la
 *          normalisation des types (nombres vs chaînes des formulaires)
 * @param {File} eleFile - fichier ELE (liste éléments → numéro RC)
 * @param {File[]} lcFiles - fichiers de cas de charge Ansys (un par CdC)
 * @returns {Promise<object>} CalculationResponse — voir models.py
 *
 * Lève une erreur axios en cas d'échec (400/422/500) ; utiliser
 * `getErrorMessage(error)` pour extraire un message lisible côté UI.
 */
export async function runCalculation(payload, eleFile, lcFiles) {
  const form = new FormData()
  form.append('request', JSON.stringify(payload))
  form.append('ele_file', eleFile)
  for (const f of lcFiles) {
    form.append('lc_files', f)
  }

  const { data } = await apiClient.post('/calculate', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Extrait un message d'erreur lisible d'une erreur axios.
 *
 * Le backend renvoie soit :
 *   - {"detail": "message"}                          (HTTPException — 400/404/500)
 *   - {"detail": [{"loc":[...], "msg":"...", ...}]}   (erreur de validation Pydantic — 422)
 *
 * @param {unknown} error
 * @returns {string}
 */
export function getErrorMessage(error) {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const loc = Array.isArray(e.loc) ? e.loc.join(' → ') : ''
        return loc ? `${loc} : ${e.msg}` : e.msg
      })
      .join('\n')
  }

  if (error?.message === 'Network Error') {
    return "Impossible de contacter le serveur de calcul. Vérifiez votre connexion ou réessayez plus tard."
  }

  return error?.message ?? 'Erreur inconnue.'
}
