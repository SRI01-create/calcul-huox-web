// Phase 23 — Résultats Format 2 : tableau détaillé par élément × cas de charge.
//
// Une ligne par combinaison (élément × CdC).
// Données : store.result.format2 (liste de ElementLCResult),
// déjà triée (rc_number, element_id, lc_name) par le backend — rc_number est
// un identifiant texte libre (Phase 28) : tri alphabétique simple, pas numérique.
//
// Fonctionnalités :
//   • Filtres : RC | classe de section | seuil ratio MAX
//   • Compteur de lignes filtrées / total
//   • Pagination ajustable (25 / 100 / 200 lignes par page)
//   • Code couleur ratios identique au Format 1  (text-ratio-*)
//   • Cellule « — » pour ratio None (vérification hors-portée)

import React, { useState, useMemo } from 'react'
import { useStore } from '../store'

// ─── Helpers de formatage ─────────────────────────────────────────────────────

const kN  = (v) => v != null ? (v / 1e3).toFixed(1) : '—'  // N   → kN
const kNm = (v) => v != null ? (v / 1e3).toFixed(1) : '—'  // N·m → kN·m

// ─── Code couleur ratio ───────────────────────────────────────────────────────

function ratioClasses(v) {
  if (v == null) return 'bg-gray-50 text-gray-300'
  if (v > 1.0)  return 'bg-red-100   text-ratio-over   font-bold'
  if (v >= 0.9) return 'bg-orange-50 text-ratio-danger font-semibold'
  if (v >= 0.5) return 'bg-yellow-50 text-ratio-warning'
  return               'bg-green-50  text-ratio-ok'
}

function RatioTd({ value }) {
  return (
    <td className={`px-1.5 py-1 text-center text-xs tabular-nums ${ratioClasses(value)}`}>
      {value != null ? value.toFixed(3) : '—'}
    </td>
  )
}

function MaxRatioTd({ value }) {
  return (
    <td className={`px-2 py-1 text-center text-xs font-bold tabular-nums ${ratioClasses(value)}`}>
      {value != null ? value.toFixed(3) : '—'}
    </td>
  )
}

// ─── 14 ratios AllRatios ──────────────────────────────────────────────────────

const RATIOS = [
  { key: 'ratio_N',      label: 'N',    title: 'NEd / Nt,Rd ou NEd / Nc,Rd  —  §6.2.3/4' },
  { key: 'ratio_Vy',    label: 'Vy',   title: 'Vy,Ed / Vpl,y,Rd  —  §6.2.6' },
  { key: 'ratio_Vz',    label: 'Vz',   title: 'Vz,Ed / Vpl,z,Rd  —  §6.2.6' },
  { key: 'ratio_T',     label: 'T',    title: 'τ / τ_Rd  —  torsion  §6.2.7' },
  { key: 'ratio_cy',    label: 'cy',   title: 'My,Ed / My,c,Rd  —  flexion section  §6.2.5' },
  { key: 'ratio_cz',    label: 'cz',   title: 'Mz,Ed / Mz,c,Rd  —  flexion section  §6.2.5' },
  { key: 'ratio_VyT',   label: 'VyT',  title: 'Vy,Ed / Vy,pl,T,Rd  —  cisaillement réduit torsion y' },
  { key: 'ratio_VzT',   label: 'VzT',  title: 'Vz,Ed / Vz,pl,T,Rd  —  cisaillement réduit torsion z' },
  { key: 'ratio_cVN',   label: 'N+M',  title: 'Interaction N + V + M section  —  §6.2' },
  { key: 'ratio_Nb_F',  label: 'Nb,F', title: 'NEd / min(Nb,y,Rd, Nb,z,Rd)  —  flambement flexion  §6.3.1' },
  { key: 'ratio_Nb_TF', label: 'NbTF', title: 'NEd / Nb,TF,Rd  —  torsion-flexion (U uniquement)  §6.3.1' },
  { key: 'ratio_Mb',    label: 'Mb',   title: 'My,Ed / Mb,Rd  —  déversement  §6.3.2' },
  { key: 'ratio_MNy_b', label: 'MNy',  title: '§6.3.3 éq. 6.61  (CW)  —  interaction flambement + déversement' },
  { key: 'ratio_MNz_b', label: 'MNz',  title: '§6.3.3 éq. 6.62  (CX)  —  interaction flambement + déversement' },
]

// ─── Badges (identiques à Format 1) ──────────────────────────────────────────

// Glyphe selon type ET forme réelle (Phase 31) — voir ResultsFormat1.jsx.
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
  const p = {
    H: 'bg-blue-100 text-blue-800',
    U: 'bg-violet-100 text-violet-800',
    O: 'bg-teal-100 text-teal-800',
    X: 'bg-orange-100 text-orange-800',
  }
  const { glyph, title } = shapeFlag(type, isAngle, isCircular)
  return (
    <span className={`px-1.5 py-0.5 rounded text-[11px] font-bold
                      ${p[type] ?? 'bg-gray-100 text-gray-600'}`} title={title}>
      {glyph}
    </span>
  )
}

function ClassBadge({ cls }) {
  const n = parseInt(cls)
  const p = {
    1: 'bg-green-100  text-green-800',
    2: 'bg-lime-100   text-lime-800',
    3: 'bg-yellow-100 text-yellow-800',
    4: 'bg-red-100    text-red-700 font-bold',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold
                      ${p[n] ?? 'bg-gray-100 text-gray-600'}`}>
      {cls}
    </span>
  )
}

// ─── Sous-composants tableau ──────────────────────────────────────────────────

function GroupTh({ label, cols, first = false }) {
  return (
    <th colSpan={cols}
      className={`px-3 py-1.5 text-left text-[11px] font-semibold tracking-wide
                  text-white bg-slate-700
                  ${first ? '' : 'border-l border-slate-500'}`}>
      {label}
    </th>
  )
}

function Th({ children, title, cls = '' }) {
  return (
    <th title={title}
      className={`px-2 py-1.5 whitespace-nowrap text-left text-[11px] font-semibold
                  text-slate-600 bg-slate-100 border-b border-slate-200 ${cls}`}>
      {children}
    </th>
  )
}

function Td({ children, cls = '' }) {
  return (
    <td className={`px-2 py-1.5 whitespace-nowrap text-xs text-slate-700 ${cls}`}>
      {children}
    </td>
  )
}

// ─── Constantes de filtre et pagination ──────────────────────────────────────

const THRESHOLD_BTNS = [
  { label: 'Tous',    value: 0     },
  { label: '≥ 0,50', value: 0.5   },
  { label: '≥ 0,90', value: 0.9   },
  { label: '> 1,00', value: 1.001 },
]

const PAGE_SIZES = [25, 100, 200]

// ─── Composant principal ──────────────────────────────────────────────────────

export default function ResultsFormat2() {
  const result = useStore((s) => s.result)

  const [filterRC,       setFilterRC]       = useState('all')
  const [filterClass,    setFilterClass]    = useState('all')
  const [filterMinRatio, setFilterMinRatio] = useState(0)
  const [page,           setPage]           = useState(1)
  const [pageSize,       setPageSize]       = useState(100)

  // Format1 gère déjà l'état vide — ici on retourne null si pas de résultat
  if (!result) return null

  const { format2 } = result

  if (!format2 || format2.length === 0) {
    return (
      <p className="text-sm text-gray-400 italic py-6 text-center">
        Aucun résultat Format 2.
      </p>
    )
  }

  // ── Options de filtre déduites des données ────────────────────────────────

  const rcOptions = useMemo(
    () => [...new Set(format2.map((r) => r.rc_number))].sort(),
    [format2],
  )

  const classOptions = useMemo(
    () => [...new Set(format2.map((r) => r.section_class))].sort(),
    [format2],
  )

  // ── Filtrage ──────────────────────────────────────────────────────────────

  const filtered = useMemo(() => {
    return format2.filter((row) => {
      if (filterRC !== 'all' && row.rc_number !== filterRC) return false
      if (filterClass !== 'all' && row.section_class !== filterClass)  return false
      if (filterMinRatio > 0 && (row.max_ratio ?? 0) < filterMinRatio) return false
      return true
    })
  }, [format2, filterRC, filterClass, filterMinRatio])

  // ── Pagination ────────────────────────────────────────────────────────────

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage   = Math.min(page, totalPages)
  const start      = (safePage - 1) * pageSize
  const paginated  = filtered.slice(start, start + pageSize)

  // Reset page=1 à chaque changement de filtre ou taille de page
  function setFilter(setter) {
    return (val) => { setter(val); setPage(1) }
  }

  function resetFilters() {
    setFilterRC('all'); setFilterClass('all'); setFilterMinRatio(0); setPage(1)
  }

  const isFiltered = filterRC !== 'all' || filterClass !== 'all' || filterMinRatio > 0

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4 mt-10 pt-8 border-t border-gray-200">

      {/* ── En-tête ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            Détail par élément × cas de charge
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Format 2 — Les 14 ratios EC3 pour chaque combinaison élément × CdC.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500 pt-1.5">
          <span className={`font-bold tabular-nums ${isFiltered ? 'text-slate-800' : ''}`}>
            {filtered.length.toLocaleString('fr-FR')}
          </span>
          <span>/ {format2.length.toLocaleString('fr-FR')} ligne{format2.length > 1 ? 's' : ''}</span>
          {isFiltered && (
            <button
              onClick={resetFilters}
              className="ml-1.5 text-blue-600 hover:text-blue-800 underline
                         underline-offset-2 transition-colors">
              Réinitialiser
            </button>
          )}
        </div>
      </div>

      {/* ── Barre de filtres ──────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 bg-slate-50
                      border border-slate-200 rounded-lg px-4 py-3">

        {/* RC */}
        <label className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-600">RC</span>
          <select
            value={filterRC}
            onChange={(e) => setFilter(setFilterRC)(e.target.value)}
            className="text-xs border border-slate-300 rounded px-2 py-1 bg-white
                       text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-400">
            <option value="all">Tous</option>
            {rcOptions.map((rc) => (
              <option key={rc} value={rc}>RC {rc}</option>
            ))}
          </select>
        </label>

        <div className="h-5 border-l border-slate-300 hidden sm:block" />

        {/* Classe */}
        <label className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-600">Classe</span>
          <select
            value={filterClass}
            onChange={(e) => setFilter(setFilterClass)(e.target.value)}
            className="text-xs border border-slate-300 rounded px-2 py-1 bg-white
                       text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-400">
            <option value="all">Toutes</option>
            {classOptions.map((c) => (
              <option key={c} value={c}>Classe {c}</option>
            ))}
          </select>
        </label>

        <div className="h-5 border-l border-slate-300 hidden sm:block" />

        {/* Seuil ratio */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-600">Seuil MAX</span>
          <div className="flex gap-1">
            {THRESHOLD_BTNS.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => setFilter(setFilterMinRatio)(value)}
                className={`px-2 py-0.5 rounded text-xs transition-colors border ${
                  filterMinRatio === value
                    ? 'bg-slate-700 text-white border-slate-700 font-semibold'
                    : 'bg-white border-slate-300 text-slate-600 hover:border-slate-500'
                }`}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Tableau ───────────────────────────────────────────────────────── */}
      {paginated.length === 0 ? (
        <p className="text-sm text-gray-400 italic py-8 text-center">
          Aucune ligne ne correspond aux filtres actifs.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
          <table className="text-xs border-collapse min-w-max">

            <thead>
              {/* Ligne 1 — groupes */}
              <tr>
                <GroupTh label="Identification"             cols={6} first />
                <GroupTh label="Efforts internes"           cols={3} />
                <GroupTh label="Ratios EC3  (§6.2 / §6.3)" cols={14} />
                <GroupTh label=""                           cols={1} />
              </tr>

              {/* Ligne 2 — colonnes individuelles */}
              <tr>
                <Th title="Groupe RC">RC</Th>
                <Th title="Identifiant numérique de l'élément" cls="text-right">Élém.</Th>
                <Th title="Nom du cas de charge (issu du nom de fichier LC)"
                    cls="min-w-[90px]">CdC</Th>
                <Th title="Type de section  (H / U / O / X)" cls="text-center">Type</Th>
                <Th title="Désignation de la section" cls="min-w-[100px]">Section</Th>
                <Th title="Classe de section EC3  (1 à 4)" cls="text-center">Cl.</Th>
                {/* Efforts */}
                <Th title="Effort normal de compression NEd,c (kN)" cls="text-right">NEd,c</Th>
                <Th title="Moment fléchissant My,Ed (kN·m)" cls="text-right">My,Ed</Th>
                <Th title="Moment fléchissant Mz,Ed (kN·m)" cls="text-right">Mz,Ed</Th>
                {/* 14 ratios */}
                {RATIOS.map(({ label, title }) => (
                  <Th key={label} title={title} cls="text-center min-w-[40px]">
                    {label}
                  </Th>
                ))}
                {/* MAX */}
                <Th title="Ratio maximal sur cette combinaison" cls="text-center min-w-[52px]">
                  MAX
                </Th>
              </tr>
            </thead>

            <tbody>
              {paginated.map((row, idx) => {
                const r = row.ratios ?? {}
                return (
                  <tr
                    key={`${row.rc_number}-${row.element_id}-${row.lc_name}-${idx}`}
                    className="border-t border-gray-100 hover:bg-slate-50/70 transition-colors">

                    {/* Identification */}
                    <Td cls="font-semibold text-slate-800 tabular-nums">
                      {row.rc_number}
                    </Td>
                    <Td cls="text-right tabular-nums">{row.element_id}</Td>
                    <Td cls="font-mono text-slate-600 text-[11px]">{row.lc_name}</Td>
                    <Td cls="text-center">
                      <TypeBadge type={row.section_type} isAngle={row.is_angle} isCircular={row.is_circular} />
                    </Td>
                    <Td cls="font-medium text-slate-700">
                      {row.designation}
                      {row.is_welded && (
                        <span className="ml-1.5 text-[10px] bg-amber-100 text-amber-700
                                         px-1 py-0.5 rounded" title="Section soudée (PRS)">
                          PRS
                        </span>
                      )}
                    </Td>
                    <Td cls="text-center">
                      <ClassBadge cls={row.section_class} />
                    </Td>

                    {/* Efforts internes */}
                    <Td cls="text-right tabular-nums">{kN(row.NEd_c)}</Td>
                    <Td cls="text-right tabular-nums">{kNm(row.My_Ed)}</Td>
                    <Td cls="text-right tabular-nums">{kNm(row.Mz_Ed)}</Td>

                    {/* 14 ratios */}
                    {RATIOS.map(({ key }) => (
                      <RatioTd key={key} value={r[key] ?? null} />
                    ))}

                    {/* MAX */}
                    <MaxRatioTd value={row.max_ratio} />
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Pagination ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">

        {/* Sélecteur taille de page */}
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <span>Lignes par page :</span>
          {PAGE_SIZES.map((s) => (
            <button
              key={s}
              onClick={() => { setPageSize(s); setPage(1) }}
              className={`px-2 py-0.5 rounded border text-xs transition-colors ${
                pageSize === s
                  ? 'bg-slate-700 text-white border-slate-700 font-semibold'
                  : 'border-slate-300 text-slate-600 hover:border-slate-500 bg-white'
              }`}>
              {s}
            </button>
          ))}
        </div>

        {/* Navigation pages */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(1)}
              disabled={safePage === 1}
              className="px-2 py-1 rounded border border-slate-300 text-xs text-slate-600
                         hover:border-slate-500 disabled:opacity-30 disabled:cursor-not-allowed
                         bg-white transition-colors">
              «
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage === 1}
              className="px-3 py-1 rounded border border-slate-300 text-xs text-slate-600
                         hover:border-slate-500 disabled:opacity-30 disabled:cursor-not-allowed
                         bg-white transition-colors">
              ← Préc.
            </button>
            <span className="text-xs text-slate-600 tabular-nums px-1">
              Page <strong>{safePage}</strong> / {totalPages}
              <span className="ml-2 text-slate-400">
                (lignes {start + 1}–{Math.min(start + pageSize, filtered.length)})
              </span>
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage === totalPages}
              className="px-3 py-1 rounded border border-slate-300 text-xs text-slate-600
                         hover:border-slate-500 disabled:opacity-30 disabled:cursor-not-allowed
                         bg-white transition-colors">
              Suiv. →
            </button>
            <button
              onClick={() => setPage(totalPages)}
              disabled={safePage === totalPages}
              className="px-2 py-1 rounded border border-slate-300 text-xs text-slate-600
                         hover:border-slate-500 disabled:opacity-30 disabled:cursor-not-allowed
                         bg-white transition-colors">
              »
            </button>
          </div>
        )}
      </div>

      {/* ── Légende ───────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2.5 text-xs text-gray-500 pb-2">
        <span className="font-medium">Ratios :</span>
        {[
          { bg: 'bg-green-50',  text: 'text-ratio-ok',                   label: '< 0,50' },
          { bg: 'bg-yellow-50', text: 'text-ratio-warning',               label: '0,50 – 0,90' },
          { bg: 'bg-orange-50', text: 'text-ratio-danger font-semibold',  label: '0,90 – 1,00' },
          { bg: 'bg-red-100',   text: 'text-ratio-over font-bold',        label: '> 1,00' },
          { bg: 'bg-gray-50',   text: 'text-gray-300',                    label: 'N/A' },
        ].map(({ bg, text, label }) => (
          <span key={label} className={`px-2 py-0.5 rounded ${bg} ${text}`}>{label}</span>
        ))}
        <span className="text-gray-300 mx-1">|</span>
        <span className="text-gray-400">
          Survolez les en-têtes pour les tooltips EC3.
        </span>
      </div>

    </div>
  )
}
