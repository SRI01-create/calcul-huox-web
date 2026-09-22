// Phase 33 — Vue tableau compacte des RC, en remplacement de l'empilement de
// cartes (page "1 — Configuration RC & Matériaux" devenue trop lourde avec
// beaucoup de RC configurés).
//
// Une ligne résumée par RC (numéro, section, matériau, classe, longueur) ;
// un clic sur la ligne (ou le chevron) déplie la carte complète existante
// (RCRow, inchangée) juste dessous — l'édition se fait toujours dans RCRow,
// cette vue ne fait qu'aider à naviguer parmi de nombreux RC sans tout
// afficher en permanence.
//
// Volontairement pas de récupération des propriétés catalogue (is_welded/
// is_angle/is_circular) pour le badge de type dans la ligne résumée — ça
// demanderait un appel réseau par ligne juste pour l'aperçu. Le badge
// détaillé (U/L, O/□, X/■●, [PRS]) reste visible une fois la ligne dépliée
// (RCRow → SectionPicker → ShapeFlags), avec des vraies données.

import React, { useState } from 'react'
import { useStore } from '../store'
import RCRow from './RCRow'

const TYPE_COLORS = {
  H: 'bg-blue-100 text-blue-800',
  U: 'bg-violet-100 text-violet-800',
  O: 'bg-teal-100 text-teal-800',
  X: 'bg-orange-100 text-orange-800',
}

export default function RCTable({ rcConfigs, materials }) {
  const removeRC = useStore((s) => s.removeRC)
  const [expandedUids, setExpandedUids] = useState(() => new Set())

  const toggle = (uid) => {
    setExpandedUids((prev) => {
      const next = new Set(prev)
      if (next.has(uid)) next.delete(uid)
      else next.add(uid)
      return next
    })
  }

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wide">
            <th className="px-3 py-2 w-6"></th>
            <th className="px-3 py-2">RC</th>
            <th className="px-3 py-2">Section</th>
            <th className="px-3 py-2">Matériau</th>
            <th className="px-3 py-2">Classe</th>
            <th className="px-3 py-2">L (<span className="lowercase">m</span>)</th>
            <th className="px-3 py-2 w-8"></th>
          </tr>
        </thead>
        <tbody>
          {rcConfigs.map((rc) => {
            const isOpen = expandedUids.has(rc._uid)
            const material = materials.find((m) => m.material_number === rc.material_number)
            const isCustom = rc.custom_section != null

            return (
              <React.Fragment key={rc._uid}>
                <tr
                  className="border-t border-gray-100 hover:bg-slate-50 cursor-pointer"
                  onClick={() => toggle(rc._uid)}
                >
                  <td className="px-3 py-2 text-gray-400 text-base">{isOpen ? '▾' : '▸'}</td>
                  <td className="px-3 py-2 font-medium text-slate-800 whitespace-nowrap">
                    {rc.rc_number || '—'}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-bold mr-1.5 ${
                        TYPE_COLORS[rc.section_type] ?? 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {rc.section_type}
                    </span>
                    <span className="text-gray-700">
                      {rc.designation || <span className="italic text-gray-400">non renseignée</span>}
                    </span>
                    {isCustom && (
                      <span className="ml-1.5 text-[10px] bg-amber-100 text-amber-700 px-1 py-0.5 rounded">
                        perso
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                    {material ? material.designation : <span className="italic text-gray-400">—</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                    {rc.manual_section_class ? `manuel : ${rc.manual_section_class}` : 'auto'}
                  </td>
                  <td className="px-3 py-2 text-gray-600">{rc.L !== '' ? rc.L : '—'}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); removeRC(rc._uid) }}
                      className="text-gray-400 hover:text-red-600 text-lg leading-none"
                      title="Supprimer ce RC"
                    >
                      ×
                    </button>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="border-t border-gray-100">
                    <td colSpan={7} className="p-0">
                      <div className="p-3 bg-slate-50/60">
                        <RCRow rc={rc} />
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
