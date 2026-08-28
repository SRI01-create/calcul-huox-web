// Phase 20 — Liste des RC (Regroupements de Calcul) — étape 1, Configuration.

import React from 'react'
import { useStore } from '../store'
import RCRow from './RCRow'

export default function RCForm() {
  const rcConfigs = useStore((s) => s.rcConfigs)
  const materials = useStore((s) => s.materials)
  const addRC = useStore((s) => s.addRC)

  // Doublons de numéro RC — alerte locale immédiate.
  const numbers = rcConfigs.map((rc) => rc.rc_number)
  const duplicates = [...new Set(numbers.filter((n, i) => numbers.indexOf(n) !== i))]

  return (
    <section className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-slate-800">
          Regroupements de calcul (RC)
        </h2>
        <button
          type="button"
          onClick={() => addRC()}
          disabled={materials.length === 0}
          className="text-sm bg-slate-700 text-white rounded px-3 py-1.5 hover:bg-slate-600 disabled:opacity-40 transition-colors"
        >
          + Ajouter un RC
        </button>
      </div>

      {materials.length === 0 && (
        <p className="text-sm text-amber-600 mb-2">
          Ajoutez au moins un matériau avant de configurer un RC.
        </p>
      )}

      {duplicates.length > 0 && (
        <p className="text-sm text-red-600 mb-2">
          Numéros de RC en double : {duplicates.join(', ')}.
        </p>
      )}

      {rcConfigs.length === 0 && (
        <p className="text-sm text-gray-400 italic">
          Aucun RC défini — chaque RC correspond à un groupe d'éléments
          partageant la même section, le même matériau et les mêmes
          paramètres de stabilité (longueurs de flambement, déversement…).
        </p>
      )}

      <div className="space-y-3">
        {rcConfigs.map((rc) => (
          <RCRow key={rc._uid} rc={rc} />
        ))}
      </div>
    </section>
  )
}
