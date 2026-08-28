// Phase 19 — État global (Zustand).
//
// Le store couvre les 3 étapes du workflow (cf. App.jsx) :
//   1. Configuration : `materials` + `rcConfigs`
//   2. Import        : `eleFile` + `lcFiles`
//   3. Résultats     : `result` (CalculationResponse), `error`, `isCalculating`
//
// Persistance
// ─────────────
//   `materials` et `rcConfigs` sont persistés dans localStorage (clé
//   "calcul-huox-config") afin de ne pas perdre la configuration au
//   rechargement de la page. Les fichiers (File) et les résultats ne sont
//   PAS persistés (File non sérialisable ; résultats potentiellement
//   volumineux et de toute façon invalidés par un changement de fichiers).
//
// Construction du payload API
// ─────────────────────────────
//   Les champs numériques des formulaires (Phase 20) peuvent transiter par
//   l'état sous forme de chaînes (valeurs d'<input>). `buildPayload()`
//   normalise tous les types juste avant l'appel API, pour rester
//   strictement conforme à CalculationRequest (Pydantic) côté backend.

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { runCalculation, getErrorMessage } from './api.js'

// ─── Identifiant technique interne (React key / clé de store) ────────────────
//
// Jamais envoyé à l'API, jamais affiché — sert uniquement à retrouver une
// ligne indépendamment de ses champs éditables (rc_number, material_number…).

function makeUid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `uid-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

// ─── Valeurs par défaut ───────────────────────────────────────────────────────

/**
 * Matériau par défaut : S235 carbone (le plus courant), avec un numéro
 * de référence fourni par l'appelant (cf. `nextMaterialNumber`).
 */
export function createDefaultMaterial(materialNumber) {
  return {
    material_number: materialNumber,
    designation: 'S235',
    fy: 235,
    fu: 360,
    E: 210000,
    G: 80769,
    steel_type: 'carbone', // 'carbone' | 'inox'
  }
}

/**
 * RC par défaut : section H non spécifiée (l'utilisateur choisit la
 * désignation), appuis simples (cry=crz=crT=1), pas de maintiens
 * intermédiaires (Lm=L), configuration LTB "3" (déversement non vérifié
 * — cas le plus défavorable pour une poutre sans charge transversale
 * stabilisante), section pleine sans trous.
 *
 * `materialNumber` doit référencer un matériau existant dans `materials`.
 *
 * `rc_number` (Phase 28) est un identifiant texte libre (≤16 caractères,
 * sans espace/tabulation — doit correspondre exactement au token de la 2ᵉ
 * colonne du fichier ELE). Par défaut, préformaté avec la numérotation
 * automatique ("1", "2"…) mais librement modifiable par l'utilisateur.
 *
 * `_uid` est un identifiant technique interne (jamais envoyé à l'API,
 * jamais affiché) utilisé comme clé React et comme clé de recherche du
 * store, indépendante de `rc_number` — pour que renommer un RC n'entraîne
 * ni démontage de son composant ni collision de clé pendant la saisie.
 */
export function createDefaultRC(rcNumber, materialNumber) {
  return {
    _uid: makeUid(),
    rc_number: String(rcNumber),
    section_type: 'H', // 'H' | 'U' | 'O' | 'X'
    designation: '',
    material_number: materialNumber,
    manual_section_class: null, // '1'|'2'|'3'|'4' si forcée par l'utilisateur, sinon null (auto)

    // Flambement par flexion
    L: 1.0,
    cry: 1.0,
    crz: 1.0,
    buckling_curve_y: 'b', // 'a'|'a0'|'b'|'c'|'d' — défaut backend pour y-y
    buckling_curve_z: 'c', // défaut backend pour z-z

    // Flambement par torsion (H, U)
    crT: 1.0,

    // Déversement (H, U)
    Lm: 1.0,
    ltb_config: '3', // '1'-'6' ou Mcr (N.m) saisi en chaîne numérique
    fabrication: 'L', // 'L' (laminé) | 'S' (PRS soudé)
    zG: 0.0,

    // Trous
    PTC: 'P', // 'P' (pleine) | 'T' (trouée A/B) | 'C' (trouée C)
    A_trou: null,
    Af_trou: null,
    kr: 1.0,
  }
}

// ─── Champs numériques (pour buildPayload) ───────────────────────────────────

const RC_INT_FIELDS = ['material_number']
const RC_FLOAT_FIELDS = ['L', 'cry', 'crz', 'crT', 'Lm', 'zG', 'kr']
const RC_NULLABLE_FLOAT_FIELDS = ['A_trou', 'Af_trou']

const MAT_INT_FIELDS = ['material_number']
const MAT_FLOAT_FIELDS = ['fy', 'fu', 'E', 'G']

/** '' | null | undefined → true (valeur "vide" d'un champ de formulaire). */
function isEmpty(v) {
  return v === '' || v === null || v === undefined
}

/** Convertit une valeur de formulaire (souvent une chaîne) en nombre. */
function toNumber(v) {
  const n = Number(v)
  return Number.isNaN(n) ? v : n
}

/**
 * Normalise un RCConfig avant envoi à l'API :
 *   - rc_number : chaîne (trim) — voir RCConfig.rc_number (Phase 28)
 *   - material_number → int
 *   - champs flottants → float
 *   - A_trou / Af_trou : '' ou null → null, sinon float
 *   - ltb_config : conservé en chaîne (trim) — accepté '1'-'6' ou Mcr numérique
 *   - _uid : identifiant technique interne, jamais envoyé à l'API
 */
function normalizeRC(rc) {
  const { _uid, ...rest } = rc
  const out = { ...rest }
  out.rc_number = String(out.rc_number ?? '').trim()
  for (const f of RC_INT_FIELDS) out[f] = toNumber(out[f])
  for (const f of RC_FLOAT_FIELDS) out[f] = toNumber(out[f])
  for (const f of RC_NULLABLE_FLOAT_FIELDS) {
    out[f] = isEmpty(out[f]) ? null : toNumber(out[f])
  }
  if (typeof out.ltb_config === 'string') out.ltb_config = out.ltb_config.trim()
  return out
}

/** Normalise un MaterialConfig avant envoi à l'API (mêmes principes que normalizeRC). */
function normalizeMaterial(mat) {
  const out = { ...mat }
  for (const f of MAT_INT_FIELDS) out[f] = toNumber(out[f])
  for (const f of MAT_FLOAT_FIELDS) out[f] = toNumber(out[f])
  return out
}

// ─── Store ─────────────────────────────────────────────────────────────────

export const useStore = create(
  persist(
    (set, get) => ({
      // ── État : configuration ────────────────────────────────────────────
      materials: [createDefaultMaterial(1)],
      rcConfigs: [createDefaultRC(1, 1)],

      // ── État : fichiers (non persistés — voir partialize ci-dessous) ────
      eleFile: null, // File | null
      lcFiles: [], // File[]

      // ── État : calcul ────────────────────────────────────────────────────
      result: null, // CalculationResponse | null
      error: null, // string | null
      isCalculating: false,

      // ── Sélecteurs simples ────────────────────────────────────────────────

      /** Prochain numéro de matériau libre (max existant + 1, 1 si vide). */
      nextMaterialNumber: () => {
        const { materials } = get()
        if (materials.length === 0) return 1
        return Math.max(...materials.map((m) => Number(m.material_number) || 0)) + 1
      },

      /** Prochain numéro de RC libre (max existant + 1, 1 si vide). */
      nextRcNumber: () => {
        const { rcConfigs } = get()
        if (rcConfigs.length === 0) return 1
        return Math.max(...rcConfigs.map((r) => Number(r.rc_number) || 0)) + 1
      },

      // ── Actions : matériaux ────────────────────────────────────────────────

      /** Ajoute un matériau S235 carbone avec le prochain numéro libre. */
      addMaterial: () => {
        const num = get().nextMaterialNumber()
        set((state) => ({
          materials: [...state.materials, createDefaultMaterial(num)],
        }))
        return num
      },

      /** Met à jour un ou plusieurs champs du matériau `materialNumber`. */
      updateMaterial: (materialNumber, patch) => {
        set((state) => ({
          materials: state.materials.map((m) =>
            m.material_number === materialNumber ? { ...m, ...patch } : m
          ),
        }))
      },

      /**
       * Supprime un matériau, sauf s'il est référencé par au moins un RC
       * (le backend rejetterait la requête — on prévient l'utilisateur en
       * amont). Retourne `{ ok: true }` ou `{ ok: false, error: string }`.
       */
      removeMaterial: (materialNumber) => {
        const { materials, rcConfigs } = get()
        if (materials.length <= 1) {
          return { ok: false, error: 'Au moins un matériau est requis.' }
        }
        const usedBy = rcConfigs
          .filter((rc) => rc.material_number === materialNumber)
          .map((rc) => rc.rc_number)
        if (usedBy.length > 0) {
          return {
            ok: false,
            error: `Matériau n°${materialNumber} utilisé par RC ${usedBy.join(', ')} — impossible de le supprimer.`,
          }
        }
        set((state) => ({
          materials: state.materials.filter((m) => m.material_number !== materialNumber),
        }))
        return { ok: true }
      },

      // ── Actions : configurations RC ─────────────────────────────────────────

      /**
       * Ajoute un RC avec le prochain numéro libre, référençant le premier
       * matériau disponible (ou celui passé en paramètre).
       */
      addRC: (materialNumber) => {
        const { materials } = get()
        const num = get().nextRcNumber()
        const matNum = materialNumber ?? materials[0]?.material_number ?? 1
        const rc = createDefaultRC(num, matNum)
        set((state) => ({
          rcConfigs: [...state.rcConfigs, rc],
        }))
        return rc._uid
      },

      /** Met à jour un ou plusieurs champs du RC identifié par `uid` (interne — cf. `_uid`). */
      updateRC: (uid, patch) => {
        set((state) => ({
          rcConfigs: state.rcConfigs.map((rc) =>
            rc._uid === uid ? { ...rc, ...patch } : rc
          ),
        }))
      },

      /** Supprime le RC identifié par `uid` (interne — cf. `_uid`). */
      removeRC: (uid) => {
        set((state) => ({
          rcConfigs: state.rcConfigs.filter((rc) => rc._uid !== uid),
        }))
      },

      // ── Actions : fichiers ────────────────────────────────────────────────

      /** Définit le fichier ELE (liste éléments → numéro RC). */
      setEleFile: (file) => set({ eleFile: file }),

      /** Remplace la liste des fichiers de cas de charge. */
      setLcFiles: (files) => set({ lcFiles: Array.from(files) }),

      /** Ajoute des fichiers de cas de charge à la liste existante. */
      addLcFiles: (files) => {
        set((state) => ({ lcFiles: [...state.lcFiles, ...Array.from(files)] }))
      },

      /** Retire un fichier de cas de charge par son nom. */
      removeLcFile: (filename) => {
        set((state) => ({
          lcFiles: state.lcFiles.filter((f) => f.name !== filename),
        }))
      },

      // ── Validation locale (avant appel API) ──────────────────────────────

      /**
       * Vérifie la cohérence de la configuration courante, sans appel
       * réseau. Reproduit les contraintes principales du backend
       * (CalculationRequest.validate_material_refs, RCConfig.validate_holes,
       * unicité des numéros) pour donner un retour immédiat à l'utilisateur.
       *
       * @returns {string[]} liste des erreurs (vide si tout est valide)
       */
       getValidationErrors: () => {
        const { materials, rcConfigs, eleFile, lcFiles } = get()
        const errors = []

        // ── Matériaux ──────────────────────────────────────────────────────
        if (materials.length === 0) {
          errors.push('Au moins un matériau doit être défini.')
        }
        const matNumbers = materials.map((m) => m.material_number)
        const dupMat = matNumbers.filter((n, i) => matNumbers.indexOf(n) !== i)
        if (dupMat.length > 0) {
          errors.push(`Numéros de matériau en double : ${[...new Set(dupMat)].join(', ')}.`)
        }

        // ── RC ───────────────────────────────────────────────────────────────
        if (rcConfigs.length === 0) {
          errors.push('Au moins une configuration RC doit être définie.')
        }
        const rcNumbers = rcConfigs.map((rc) => rc.rc_number)
        const dupRc = rcNumbers.filter((n, i) => rcNumbers.indexOf(n) !== i)
        if (dupRc.length > 0) {
          errors.push(`Numéros de RC en double : ${[...new Set(dupRc)].join(', ')}.`)
        }

        const matNumberSet = new Set(matNumbers)
        for (const rc of rcConfigs) {
          const rcId = typeof rc.rc_number === 'string' ? rc.rc_number.trim() : rc.rc_number
          if (!rcId) {
            errors.push('RC : l\'identifiant ne peut pas être vide.')
          } else {
            if (/\s/.test(rcId)) {
              errors.push(
                `RC "${rcId}" : l'identifiant ne peut pas contenir d'espace ni de `
                + `tabulation (contrainte du format du fichier ELE) — utiliser '-' ou '_' à la place.`
              )
            }
            if (rcId.length > 16) {
              errors.push(`RC "${rcId}" : l'identifiant dépasse 16 caractères.`)
            }
          }
          if (!rc.designation || rc.designation.trim() === '') {
            errors.push(`RC ${rc.rc_number} : aucune désignation de section sélectionnée.`)
          }
          if (!matNumberSet.has(rc.material_number)) {
            errors.push(
              `RC ${rc.rc_number} : matériau n°${rc.material_number} introuvable.`
            )
          }
          if ((rc.PTC === 'T' || rc.PTC === 'C') && (isEmpty(rc.A_trou) || Number(rc.A_trou) === 0)) {
            errors.push(
              `RC ${rc.rc_number} : "Aire des trous" (A_trou) requise et non nulle pour PTC = '${rc.PTC}'.`
            )
          }
        }

        // ── Fichiers ───────────────────────────────────────────────────────
        if (!eleFile) {
          errors.push('Fichier ELE (liste des éléments) manquant.')
        }
        if (lcFiles.length === 0) {
          errors.push('Aucun fichier de cas de charge fourni.')
        }

        return errors
      },

      // ── Construction du payload API ──────────────────────────────────────

      /**
       * Construit `{rc_configs, material_configs}` avec tous les champs
       * numériques correctement typés, prêt pour `JSON.stringify` +
       * `POST /api/calculate`.
       */
      buildPayload: () => {
        const { materials, rcConfigs } = get()
        return {
          rc_configs: rcConfigs.map(normalizeRC),
          material_configs: materials.map(normalizeMaterial),
        }
      },
// ── Export / Import de configuration ─────────────────────────────────

      /**
       * Construit un objet exportable {materials, rc_configs} + métadonnées,
       * destiné à être sérialisé en JSON et proposé au téléchargement.
       */
      exportConfig: () => {
        const { materials, rcConfigs } = get()
        // _uid est un détail d'implémentation interne (React/store) — pas
        // pertinent dans un fichier destiné à être relu/partagé.
        const exportableRC = rcConfigs.map(({ _uid, ...rest }) => rest)
        return {
          app: 'calcul-huox-web',
          export_version: 1,
          exported_at: new Date().toISOString(),
          materials,
          rc_configs: exportableRC,
        }
      },

      /**
       * Recharge une configuration précédemment exportée. `data` doit être
       * l'objet déjà parsé (JSON.parse fait par l'appelant). Remplace
       * entièrement `materials` et `rcConfigs` si le format est valide ;
       * ne touche à rien sinon.
       *
       * @returns {{ok: true} | {ok: false, error: string}}
       */
      importConfig: (data) => {
        if (!data || typeof data !== 'object') {
          return { ok: false, error: 'Fichier invalide : contenu non reconnu.' }
        }
        const materials = data.materials
        const rcConfigs = data.rc_configs
        if (!Array.isArray(materials) || materials.length === 0) {
          return { ok: false, error: 'Fichier invalide : aucun matériau trouvé.' }
        }
        if (!Array.isArray(rcConfigs) || rcConfigs.length === 0) {
          return { ok: false, error: 'Fichier invalide : aucune configuration RC trouvée.' }
        }
        const hasValidMaterials = materials.every(
          (m) => m && typeof m === 'object' && m.material_number !== undefined
        )
        const hasValidRC = rcConfigs.every(
          (rc) => rc && typeof rc === 'object' && rc.rc_number !== undefined
        )
        if (!hasValidMaterials || !hasValidRC) {
          return { ok: false, error: 'Fichier invalide : structure de matériau ou de RC incorrecte.' }
        }
        // Phase 28 : les exports antérieurs à `_uid` n'en ont pas — généré à
        // la volée pour éviter toute collision de clé React.
        const rcConfigsWithUid = rcConfigs.map((rc) => (rc._uid ? rc : { ...rc, _uid: makeUid() }))
        set({ materials, rcConfigs: rcConfigsWithUid, result: null, error: null })
        return { ok: true }
      },
      // ── Calcul ─────────────────────────────────────────────────────────────

      /**
       * Lance le calcul : valide localement, puis appelle POST /api/calculate.
       * Met à jour `result` / `error` / `isCalculating`.
       *
       * @returns {Promise<boolean>} true si le calcul a réussi
       */
      calculate: async () => {
        const errors = get().getValidationErrors()
        if (errors.length > 0) {
          set({ error: errors.join('\n'), result: null })
          return false
        }

        set({ isCalculating: true, error: null })
        try {
          const payload = get().buildPayload()
          const { eleFile, lcFiles } = get()
          const result = await runCalculation(payload, eleFile, lcFiles)
          set({ result, isCalculating: false, error: null })
          return true
        } catch (err) {
          set({ error: getErrorMessage(err), isCalculating: false, result: null })
          return false
        }
      },

      /** Efface le résultat et l'erreur courants (sans toucher à la configuration). */
      resetResults: () => set({ result: null, error: null }),

      /** Efface uniquement le message d'erreur courant. */
      clearError: () => set({ error: null }),

      /** Réinitialise tout l'état (nouvelle étude). */
      resetAll: () =>
        set({
          materials: [createDefaultMaterial(1)],
          rcConfigs: [createDefaultRC(1, 1)],
          eleFile: null,
          lcFiles: [],
          result: null,
          error: null,
          isCalculating: false,
        }),
    }),
    {
      name: 'calcul-huox-config',
      // Seules la configuration RC/matériaux est persistée : les fichiers
      // (non sérialisables) et les résultats (potentiellement obsolètes
      // après reprise) sont ré-initialisés à chaque chargement.
      partialize: (state) => ({
        materials: state.materials,
        rcConfigs: state.rcConfigs,
      }),
      // Phase 28 : les configurations enregistrées avant l'introduction de
      // `_uid` n'en ont pas — on le génère à la volée au chargement pour
      // éviter toute collision de clé React entre RC existants.
      merge: (persistedState, currentState) => {
        const merged = { ...currentState, ...persistedState }
        merged.rcConfigs = (merged.rcConfigs || []).map((rc) => (
          rc._uid ? rc : { ...rc, _uid: makeUid() }
        ))
        return merged
      },
    }
  )
)
