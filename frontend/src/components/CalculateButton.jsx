// Phase 21 — Bouton de lancement du calcul + retour d'état.
//
// Responsabilités :
//   1. Affiche les erreurs de validation locale (getValidationErrors) en temps
//      réel, pour permettre à l'utilisateur de corriger avant de cliquer.
//   2. Déclenche store.calculate() au clic (valide + appelle l'API).
//   3. Affiche le spinner + message "Calcul en cours…" pendant isCalculating.
//   4. Affiche l'erreur API si le calcul échoue.
//   5. Navigue vers l'onglet "results" (step 3) si le calcul réussit.
//
// `onSuccess` prop : fonction appelée par le parent (App.jsx) pour
//   setActiveStep('results') — on reste dans un composant pur sans
//   couplage direct à la logique de navigation.

import React, { useEffect } from 'react'
import { useStore } from '../store'

export default function CalculateButton({ onSuccess }) {
  const isCalculating       = useStore((s) => s.isCalculating)
  const error               = useStore((s) => s.error)
  const result              = useStore((s) => s.result)
  const calculate           = useStore((s) => s.calculate)
  const clearError          = useStore((s) => s.clearError)
  const getValidationErrors = useStore((s) => s.getValidationErrors)

  // Ces 4 lignes ne sont pas utilisées directement dans le JSX, mais elles
  // sont indispensables : sans elles, le composant ne se re-rend jamais
  // quand les fichiers ou la configuration RC/matériaux changent, et les
  // erreurs de validation affichées restent figées sur un ancien état.
  const materials = useStore((s) => s.materials)
  const rcConfigs = useStore((s) => s.rcConfigs)
  const eleFile   = useStore((s) => s.eleFile)
  const lcFiles   = useStore((s) => s.lcFiles)

  // Calculé directement au render (pas de useEffect) — évite la boucle infinie.
  // getValidationErrors() est une fonction pure synchrone (pas d'appel réseau).
  const validationErrors = getValidationErrors()

  // Navigue vers les résultats dès qu'un calcul réussit.
  useEffect(() => {
    if (result) onSuccess?.()
  }, [result])  // eslint-disable-line react-hooks/exhaustive-deps

  const hasErrors = validationErrors.length > 0

  const handleClick = async () => {
    clearError()
    await calculate()
  }

  return (
    <div className="space-y-4">

      {/* ── Erreurs de validation ──────────────────────────────────────── */}
      {hasErrors && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4">
          <p className="text-sm font-semibold text-amber-800 mb-2">
            Avant de lancer le calcul, corrigez les points suivants :
          </p>
          <ul className="space-y-1">
            {validationErrors.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-amber-700">
                <span className="mt-0.5 shrink-0">•</span>
                <span>{e}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Erreur API ────────────────────────────────────────────────── */}
      {error && !hasErrors && (
        <div className="bg-red-50 border border-red-300 rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-red-800 mb-1">
                Erreur lors du calcul
              </p>
              <pre className="text-sm text-red-700 whitespace-pre-wrap font-sans">
                {error}
              </pre>
            </div>
            <button
              type="button"
              onClick={clearError}
              className="text-red-400 hover:text-red-700 text-lg leading-none shrink-0"
              title="Fermer"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* ── Bouton principal ──────────────────────────────────────────── */}
      <button
        type="button"
        onClick={handleClick}
        disabled={isCalculating || hasErrors}
        className={`w-full flex items-center justify-center gap-3 py-3 px-6 rounded-lg text-white font-semibold text-sm transition-colors ${
          isCalculating || hasErrors
            ? 'bg-slate-400 cursor-not-allowed'
            : 'bg-slate-700 hover:bg-slate-600 active:bg-slate-800'
        }`}
      >
        {isCalculating ? (
          <>
            {/* Spinner SVG */}
            <svg className="h-5 w-5 animate-spin text-white" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10"
                stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Calcul en cours…
          </>
        ) : (
          <>
            {/* Icône éclair */}
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            Lancer le calcul EC3
          </>
        )}
      </button>

      {/* ── Note sur la durée ────────────────────────────────────────── */}
      {!isCalculating && !hasErrors && (
        <p className="text-xs text-gray-400 text-center">
          Le calcul vectorisé prend généralement moins d'une seconde pour les
          modèles courants. Un délai plus long peut indiquer un "cold start"
          du serveur hébergé sur Render.
        </p>
      )}

      {isCalculating && (
        <p className="text-xs text-slate-500 text-center animate-pulse">
          Envoi des fichiers et calcul vectorisé en cours…
        </p>
      )}
    </div>
  )
}
