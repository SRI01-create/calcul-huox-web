// Phase 20 — Ligne de configuration d'un matériau (carte dans MaterialForm).
//
// Champs édités : designation, steel_type, fy, fu, E, G
// (cf. backend/app/models.py — MaterialConfig)
//
// Un sélecteur de "préréglages" propose les nuances d'acier les plus
// courantes (valeurs de fy/fu selon NF EN 1993-1-1 Table 3.1, t≤40mm,
// et NF EN 1993-1-4 pour les inox 1.4301/1.4401 à l'état recuit) ; il
// pré-remplit les champs mais reste librement modifiable ensuite (ex.
// nuances d'épaisseur >40mm avec fy réduit).

import React from 'react'
import { useStore } from '../store'

// ─── Préréglages de nuances courantes ────────────────────────────────────────

const PRESETS = {
  S235:    { fy: 235, fu: 360, E: 210000, G: 80769, steel_type: 'carbone' },
  S275:    { fy: 275, fu: 430, E: 210000, G: 80769, steel_type: 'carbone' },
  S355:    { fy: 355, fu: 510, E: 210000, G: 80769, steel_type: 'carbone' },
  S460:    { fy: 460, fu: 540, E: 210000, G: 80769, steel_type: 'carbone' },
  '1.4301': { fy: 210, fu: 520, E: 200000, G: 76900, steel_type: 'inox' },
  '1.4401': { fy: 220, fu: 530, E: 200000, G: 76900, steel_type: 'inox' },
  '1.4571': { fy: 220, fu: 520, E: 200000, G: 76900, steel_type: 'inox' },
}

// ─── Petit champ numérique réutilisable ──────────────────────────────────────

function NumField({ label, unit, value, onChange, step = 1, min }) {
  return (
    <label className="flex flex-col text-sm">
      <span className="text-gray-600 mb-1">
        {label} {unit && <span className="text-gray-400">({unit})</span>}
      </span>
      <input
        type="number"
        className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
        value={value}
        step={step}
        min={min}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  )
}

// ─── Ligne matériau ───────────────────────────────────────────────────────────

export default function MaterialRow({ material, canRemove }) {
  const updateMaterial = useStore((s) => s.updateMaterial)
  const removeMaterial = useStore((s) => s.removeMaterial)

  const num = material.material_number

  const set = (patch) => updateMaterial(num, patch)

  const applyPreset = (key) => {
    if (!key || !PRESETS[key]) return
    set({ designation: key, ...PRESETS[key] })
  }

  const handleRemove = () => {
    const res = removeMaterial(num)
    if (!res.ok) {
      // eslint-disable-next-line no-alert
      alert(res.error)
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-700 text-white text-sm font-semibold">
          {num}
        </span>

        <select
          className="border border-gray-300 rounded px-2 py-1 text-sm ml-3"
          value=""
          onChange={(e) => applyPreset(e.target.value)}
        >
          <option value="">Préréglage…</option>
          {Object.keys(PRESETS).map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>

        <div className="flex-1" />

        <button
          type="button"
          onClick={handleRemove}
          disabled={!canRemove}
          title={canRemove ? 'Supprimer ce matériau' : 'Au moins un matériau requis'}
          className="text-gray-400 hover:text-red-600 disabled:opacity-30 disabled:hover:text-gray-400 text-lg leading-none px-2"
        >
          ×
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <label className="flex flex-col text-sm col-span-2 sm:col-span-1">
          <span className="text-gray-600 mb-1">Désignation</span>
          <input
            type="text"
            className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
            value={material.designation}
            placeholder="ex. S235"
            onChange={(e) => set({ designation: e.target.value })}
          />
        </label>

        <label className="flex flex-col text-sm">
          <span className="text-gray-600 mb-1">Type d'acier</span>
          <select
            className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
            value={material.steel_type}
            onChange={(e) => set({ steel_type: e.target.value })}
          >
            <option value="carbone">Carbone</option>
            <option value="inox">Inox</option>
          </select>
        </label>

        <NumField label="fy" unit="MPa" value={material.fy} step={1} min={0}
          onChange={(v) => set({ fy: v })} />
        <NumField label="fu" unit="MPa" value={material.fu} step={1} min={0}
          onChange={(v) => set({ fu: v })} />
        <NumField label="E" unit="MPa" value={material.E} step={1000} min={0}
          onChange={(v) => set({ E: v })} />
        <NumField label="G" unit="MPa" value={material.G} step={100} min={0}
          onChange={(v) => set({ G: v })} />
      </div>

      {material.steel_type === 'inox' && (
        <p className="mt-2 text-xs text-gray-500">
          Inox : γM0 = 1.10 (au lieu de 1.00) — appliqué automatiquement par le moteur de calcul.
        </p>
      )}
    </div>
  )
}
