// Refonte page « 3 — Résultats » — en-tête commun de la page.
//
// Reprend, inchangés, les éléments qui se trouvaient en haut de l'ancien
// ResultsFormat1 : état vide, bannière de statistiques (avec Ratio MAX global)
// et avertissements globaux. Ajoute une barre de navigation par ancres vers
// les 3 blocs (fiches par RC · synthèse · détail), qui se suivent dans cet ordre.

import React from 'react'
import { useStore } from '../store'
import { ratioClasses } from './resultsShared'

// Ancres des 3 blocs (utilisées par ResultsRCSheets / ResultsFormat1 / ResultsFormat2)
export const ANCHORS = {
  sheets:  'resultats-fiches-rc',
  summary: 'resultats-synthese-rc',
  detail:  'resultats-detail',
}

function goTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export default function ResultsOverview() {
  const result = useStore((s) => s.result)

  // ── État vide ─────────────────────────────────────────────────────────────
  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-gray-400 select-none">
        <svg className="h-14 w-14 mb-5 text-gray-200" fill="none" viewBox="0 0 24 24"
          stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1
               1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm font-medium text-gray-500">Aucun résultat à afficher.</p>
        <p className="text-xs mt-1.5 text-gray-400">
          Configurez les RC, les matériaux et les fichiers Ansys, puis lancez le calcul.
        </p>
      </div>
    )
  }

  const { format1, nb_elements, nb_load_cases, nb_combinations, warnings } = result

  if (!format1 || format1.length === 0) {
    return (
      <p className="text-sm text-gray-400 italic py-8 text-center">
        Le calcul n'a retourné aucun résultat.
      </p>
    )
  }

  // ── Ratio MAX global (sur tous les RC) ─────────────────────────────────────
  const allMaxValues = format1
    .map((rc) => rc.overall_max_ratio)
    .filter((v) => v != null)
  const globalMax = allMaxValues.length > 0 ? Math.max(...allMaxValues) : null

  return (
    <div className="space-y-5 mb-8">

      {/* ── Bannière statistiques ────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">
        {[
          { label: 'Groupes RC',    value: format1.length },
          { label: 'Éléments',      value: nb_elements },
          { label: 'Cas de charge', value: nb_load_cases },
          { label: 'Combinaisons',  value: nb_combinations },
        ].map(({ label, value }) => (
          <div key={label}
            className="flex-1 min-w-[90px] bg-white border border-gray-200
                       rounded-lg px-4 py-2.5 text-center shadow-sm">
            <p className="text-xl font-bold text-slate-800">{value ?? '—'}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}

        {/* Ratio MAX global — carte colorée */}
        {globalMax != null && (
          <div className={`flex-1 min-w-[90px] rounded-lg px-4 py-2.5 text-center
                           shadow-sm border ${ratioClasses(globalMax)}`}>
            <p className="text-xl font-bold">{globalMax.toFixed(3)}</p>
            <p className="text-xs mt-0.5 opacity-80">Ratio MAX global</p>
          </div>
        )}
      </div>

      {/* ── Avertissements globaux ───────────────────────────────────────── */}
      {warnings && warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4">
          <p className="text-sm font-semibold text-amber-800 mb-2">⚠ Avertissements</p>
          <ul className="space-y-1">
            {warnings.map((w, i) => (
              <li key={i} className="flex gap-2 text-sm text-amber-700">
                <span className="shrink-0 mt-px">•</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Navigation entre les 3 blocs ─────────────────────────────────── */}
      <nav className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
        <span className="font-medium">Aller à :</span>
        {[
          { id: ANCHORS.sheets,  label: 'Fiches par RC' },
          { id: ANCHORS.summary, label: 'Synthèse des résultats par RC' },
          { id: ANCHORS.detail,  label: 'Détail par élément × cas de charge' },
        ].map(({ id, label }) => (
          <button key={id} type="button" onClick={() => goTo(id)}
            className="px-2.5 py-1 rounded border border-slate-300 bg-white
                       hover:border-slate-500 hover:text-slate-800 transition-colors">
            {label}
          </button>
        ))}
      </nav>

    </div>
  )
}
