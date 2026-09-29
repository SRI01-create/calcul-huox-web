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
// Phase 35 : même badge de forme (U/L, O/□, X/■●, [PRS]) qu'en page
// "3 — Résultats" (ResultsFormat1/2.jsx) et qu'auparavant dans RCRow (retiré
// de là, devenu redondant — voir RCRow.jsx). Logique de glyphe dupliquée ici
// par cohérence avec le pattern déjà en place dans ces fichiers (pas de
// module partagé actuellement). Badge [froid] ajouté à côté de [PRS] pour
// les U formés à froid (fabrication === "F"), même principe.
//
// Pour une section catalogue, is_welded/is_angle/is_circular ne sont pas
// dans l'objet RC local — un appel réseau par désignation est nécessaire
// (fetchSectionProperties, le même endpoint que SectionPicker dans RCRow).
// Pour éviter un appel par ligne, un cache par désignation unique
// (`${section_type}:${designation}`) est tenu au niveau du tableau : une
// désignation partagée par plusieurs RC n'est récupérée qu'une seule fois.
// Pour une section personnalisée, aucun appel n'est nécessaire : les flags
// sont déjà dans rc.custom_section.

import React, { useState, useEffect, useRef } from 'react'
import { useStore } from '../store'
import { fetchSectionProperties } from '../api'
import RCRow from './RCRow'

const TYPE_COLORS = {
  H: 'bg-blue-100 text-blue-800',
  U: 'bg-violet-100 text-violet-800',
  O: 'bg-teal-100 text-teal-800',
  X: 'bg-orange-100 text-orange-800',
}

// Même logique de glyphe que ResultsFormat1.jsx / ResultsFormat2.jsx.
function shapeFlag(type, isAngle, isCircular) {
  if (type === 'U') return isAngle
    ? { glyph: 'L', title: 'Cornière (U)' }
    : { glyph: 'U', title: 'Section U' }
  if (type === 'O') return isCircular
    ? { glyph: 'O', title: 'Section circulaire (O)' }
    : { glyph: '□', title: 'Section creuse non circulaire (O)' }
  if (type === 'X') return isCircular
    ? { glyph: '●', title: 'Section pleine circulaire (X)' }
    : { glyph: '■', title: 'Section pleine non circulaire (X)' }
  return { glyph: type, title: 'Section H (I/H)' }
}

function TypeBadge({ type, isAngle, isCircular }) {
  const { glyph, title } = shapeFlag(type, isAngle, isCircular)
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-bold mr-1.5 ${
        TYPE_COLORS[type] ?? 'bg-gray-100 text-gray-600'
      }`}
      title={title}
    >
      {glyph}
    </span>
  )
}

export default function RCTable({ rcConfigs, materials }) {
  const removeRC = useStore((s) => s.removeRC)
  const [expandedUids, setExpandedUids] = useState(() => new Set())

  // Cache des flags de forme par désignation catalogue unique (voir
  // commentaire d'en-tête). `undefined` = pas encore demandé, `null` = tenté
  // et échoué (ex. désignation invalide), objet = flags obtenus.
  const [sectionFlags, setSectionFlags] = useState({})
  const fetchingRef = useRef(new Set())

  useEffect(() => {
    rcConfigs.forEach((rc) => {
      if (rc.custom_section != null || !rc.designation) return
      const key = `${rc.section_type}:${rc.designation}`
      if (sectionFlags[key] !== undefined || fetchingRef.current.has(key)) return
      fetchingRef.current.add(key)
      fetchSectionProperties(rc.section_type, rc.designation)
        .then((data) => {
          setSectionFlags((prev) => ({
            ...prev,
            [key]: {
              is_welded: data.is_welded,
              is_angle: data.is_angle,
              is_circular: data.is_circular,
              fabrication: data.fabrication ?? null,   // Phase 35 — U uniquement
            },
          }))
        })
        .catch(() => {
          setSectionFlags((prev) => ({ ...prev, [key]: null }))
        })
        .finally(() => {
          fetchingRef.current.delete(key)
        })
    })
  }, [rcConfigs, sectionFlags])

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

            const flags = isCustom
              ? {
                  is_welded: rc.custom_section.is_welded,
                  is_angle: rc.custom_section.is_angle,
                  is_circular: rc.custom_section.is_circular,
                  fabrication: rc.custom_section.fabrication ?? null,
                }
              : rc.designation
              ? sectionFlags[`${rc.section_type}:${rc.designation}`] || null
              : null

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
                    <TypeBadge
                      type={rc.section_type}
                      isAngle={flags?.is_angle}
                      isCircular={flags?.is_circular}
                    />
                    <span className="text-gray-700">
                      {rc.designation || <span className="italic text-gray-400">non renseignée</span>}
                    </span>
                    {flags?.is_welded && (
                      <span
                        className="ml-1.5 text-[10px] bg-amber-100 text-amber-700 px-1 py-0.5 rounded"
                        title="Section soudée (PRS)"
                      >
                        PRS
                      </span>
                    )}
                    {flags?.fabrication === 'F' && (
                      <span
                        className="ml-1.5 text-[10px] bg-cyan-100 text-cyan-700 px-1 py-0.5 rounded"
                        title="Section formée à froid"
                      >
                        froid
                      </span>
                    )}
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
