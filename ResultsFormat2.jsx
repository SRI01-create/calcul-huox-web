// Refonte page « 3 — Résultats » — bloc 3 : détail par élément × cas de charge.
//
// Une ligne par combinaison (élément × CdC), 4 groupes de colonnes :
//   Identification · Dispenses · Efforts et moments maximaux · Ratios maximaux
// Données : store.result.format2 (liste de ElementLCResult),
// déjà triée (rc_number, element_id, lc_name) par le backend — rc_number est
// un identifiant texte libre (Phase 28) : tri alphabétique simple, pas numérique.
//
// Fonctionnalités :
//   • Filtres : RC | seuil ratio MAX   (le filtre par classe a été retiré avec
//     la colonne « Cl. », refonte page Résultats)
//   • Compteur de lignes filtrées / total
//   • Pagination ajustable (25 / 100 / 200 lignes par page)
//   • Code couleur ratios identique à la synthèse  (text-ratio-*)
//   • Cellule « — » pour ratio None (vérification hors-portée)
// Unités : efforts en kN, moments en kN·m.

import React, { useState, useMemo } from 'react'
import { useStore } from '../store'
import {
  kN, kNm, RATIOS, RatioTd, MaxRatioTd, GroupTh, Th, Td,
  yesNoNA, TypeBadge, SectionLabel, RatioLegend,
} from './resultsShared'
import { ANCHORS } from './ResultsOverview'

// Efforts et moments maximaux : intitulés du descriptif, unité dans le titre.
const EFFORTS = [
  { label: 'NtE', unit: 'kN',   key: 'NEd_t', fmt: kN,  title: 'Effort normal de traction NEd,t' },
  { label: 'NcE', unit: 'kN',   key: 'NEd_c', fmt: kN,  title: 'Effort normal de compression NEd,c' },
  { label: 'VyE', unit: 'kN',   key: 'Vy_Ed', fmt: kN,  title: 'Effort tranchant Vy,Ed' },
  { label: 'VzE', unit: 'kN',   key: 'Vz_Ed', fmt: kN,  title: 'Effort tranchant Vz,Ed' },
  { label: 'TE',  unit: 'kN·m', key: 'TEd',   fmt: kNm, title: 'Moment de torsion TEd' },
  { label: 'MyE', unit: 'kN·m', key: 'My_Ed', fmt: kNm, title: 'Moment fléchissant My,Ed' },
  { label: 'MzE', unit: 'kN·m', key: 'Mz_Ed', fmt: kNm, title: 'Moment fléchissant Mz,Ed' },
]

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
  const [filterMinRatio, setFilterMinRatio] = useState(0)
  const [page,           setPage]           = useState(1)
  const [pageSize,       setPageSize]       = useState(100)

  const format2 = result?.format2 ?? []

  // ── Options de filtre déduites des données ────────────────────────────────
  // (hooks appelés avant tout retour anticipé — règle des hooks de React)

  const rcOptions = useMemo(
    () => [...new Set(format2.map((r) => r.rc_number))].sort(),
    [format2],
  )

  // ── Filtrage ──────────────────────────────────────────────────────────────

  const filtered = useMemo(() => {
    return format2.filter((row) => {
      if (filterRC !== 'all' && row.rc_number !== filterRC) return false
      if (filterMinRatio > 0 && (row.max_ratio ?? 0) < filterMinRatio) return false
      return true
    })
  }, [format2, filterRC, filterMinRatio])

  // Synthèse affichée en haut de page : on ne rend rien sans résultat
  if (!result) return null

  if (format2.length === 0) {
    return (
      <p className="text-sm text-gray-400 italic py-6 text-center">
        Aucun résultat détaillé.
      </p>
    )
  }

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
    setFilterRC('all'); setFilterMinRatio(0); setPage(1)
  }

  const isFiltered = filterRC !== 'all' || filterMinRatio > 0

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <section id={ANCHORS.detail}
      className="space-y-4 mt-10 pt-8 border-t border-gray-200 scroll-mt-4">

      {/* ── En-tête ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            Détail par élément × cas de charge
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Les 14 ratios EC3 pour chaque combinaison élément × CdC.
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
                <GroupTh label="Identification"              cols={5} first />
                <GroupTh label="Dispenses"                   cols={2} />
                <GroupTh label="Efforts et moments maximaux" cols={EFFORTS.length} />
                <GroupTh label="Ratios maximaux"             cols={RATIOS.length + 1} />
              </tr>

              {/* Ligne 2 — colonnes individuelles */}
              <tr>
                {/* Identification */}
                <Th title="Groupe RC">RC</Th>
                <Th title="Identifiant numérique de l'élément" cls="text-right">Élém.</Th>
                <Th title="Nom du cas de charge (issu du nom de fichier LC)"
                    cls="min-w-[90px]">CdC</Th>
                <Th title="Type de section (flag de forme)" cls="text-center">Type</Th>
                <Th title="Désignation de la section — badges [PRS] [froid] [perso]"
                    cls="min-w-[100px]">Section</Th>
                {/* Dispenses */}
                <Th title="Possibilité de négliger les effets du flambement : λ ≤ λ0 ou NEd,c/Ncr ≤ λ0²" cls="text-center">Flamb.</Th>
                <Th title="Possibilité de négliger les effets du déversement : λLT ≤ λLT,0 ou My,Ed/Mcr ≤ λLT,0²" cls="text-center">Dévers.</Th>
                {/* Efforts et moments maximaux */}
                {EFFORTS.map(({ label, unit, title }) => (
                  <Th key={label} title={`${title} (${unit})`} cls="text-right">
                    {label} <span className="font-normal text-slate-400">({unit})</span>
                  </Th>
                ))}
                {/* Ratios maximaux */}
                {RATIOS.map(({ label, title }) => (
                  <Th key={label} title={title} cls="text-center min-w-[40px]">
                    {label}
                  </Th>
                ))}
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
                    <Td cls="min-w-[100px]"><SectionLabel item={row} /></Td>

                    {/* Dispenses */}
                    <Td cls="text-center">{yesNoNA(row.buckling_ignored)}</Td>
                    <Td cls="text-center">{yesNoNA(row.LTB_ignored)}</Td>

                    {/* Efforts et moments maximaux */}
                    {EFFORTS.map(({ key, fmt }) => (
                      <Td key={key} cls="text-right tabular-nums">{fmt(row[key])}</Td>
                    ))}

                    {/* Ratios maximaux */}
                    {RATIOS.map(({ key }) => (
                      <RatioTd key={key} value={r[key] ?? null} />
                    ))}
                    <MaxRatioTd value={row.max_ratio} size="text-xs" />
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
      <RatioLegend cls="pb-2" />

    </section>
  )
}
