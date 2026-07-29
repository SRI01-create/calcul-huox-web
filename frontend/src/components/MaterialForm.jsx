// Phase 20 — Liste des matériaux (étape 1 — Configuration).

import React from 'react'
import { useStore } from '../store'
import MaterialRow from './MaterialRow'

export default function MaterialForm() {
  const materials = useStore((s) => s.materials)
  const addMaterial = useStore((s) => s.addMaterial)

  // Doublons de numéro de matériau — alerte locale immédiate.
  const numbers = materials.map((m) => m.material_number)
  const duplicates = [...new Set(numbers.filter((n, i) => numbers.indexOf(n) !== i))]

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-slate-800">Matériaux</h2>
        <button
          type="button"
          onClick={addMaterial}
          className="text-sm bg-slate-700 text-white rounded px-3 py-1.5 hover:bg-slate-600 transition-colors"
        >
          + Ajouter un matériau
        </button>
      </div>

      {duplicates.length > 0 && (
        <p className="text-sm text-red-600 mb-2">
          Numéros de matériau en double : {duplicates.join(', ')}.
        </p>
      )}

      <div className="space-y-3">
        {materials.map((m) => (
          <MaterialRow
            key={m.material_number}
            material={m}
            canRemove={materials.length > 1}
          />
        ))}
      </div>
    </section>
  )
}
