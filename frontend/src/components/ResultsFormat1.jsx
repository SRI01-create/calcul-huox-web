// Phase 22 — Résultats Format 1 : tableau synthèse par groupe RC.
//
// Une ligne par RC. Source : store.result.format1 (liste de RCSummary).
// Chaque RCSummary contient géométrie, résistances, élancements, efforts max
// et max_ratios (AllRatios) = pire combinaison éléments × CdC sur le RC.
//
// Code couleur : text-ratio-* + fonds Tailwind légers.
// Valeur null (vérification hors-portée) → cellule grisée « — ».

import React from 'react'
import { useStore } from '../store'

// ─── Helpers de formatage ─────────────────────────────────────────────────────

const kN   = (v) => v != null ? (v / 1e3).toFixed(1) : '—'   // N → kN
const kNm  = (v) => v != null ? (v / 1e3).toFixed(1) : '—'   // N·m → kN·m
const nd   = (v) => v != null ? v.toFixed(3) : '—'            // adim., 3 décimales
const mm_  = (v) => v != null ? Math.round(v).toString() : '—' // mm, arrondi
const cm2_ = (v) => v != null ? (v * 1e4).toFixed(1) : '—'   // m² → cm²

// ─── Code couleur pour un ratio ───────────────────────────────────────────────

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
    <td className={`px-2 py-1 text-center text-sm font-bold tabular-nums ${ratioClasses(value)}`}>
      {value != null ? value.toFixed(3) : '—'}
    </td>
  )
}

// ─── Définition des 14 ratios AllRatios ───────────────────────────────────────

const RATIOS = [
  { key: 'ratio_N',     label: 'N',     title: 'NEd / Nt,Rd ou NEd / Nc,Rd  —  §6.2.3/4' },
  { key: 'ratio_Vy',   label: 'Vy',    title: 'Vy,Ed / Vpl,y,Rd  —  §6.2.6' },
  { key: 'ratio_Vz',   label: 'Vz',    title: 'Vz,Ed / Vpl,z,Rd  —  §6.2.6' },
  { key: 'ratio_T',    label: 'T',     title: 'τ / τ_Rd  —  torsion  §6.2.7' },
  { key: 'ratio_cy',   label: 'cy',    title: 'My,Ed / My,c,Rd  —  flexion section  §6.2.5' },
  { key: 'ratio_cz',   label: 'cz',    title: 'Mz,Ed / Mz,c,Rd  —  flexion section  §6.2.5' },
  { key: 'ratio_VyT',  label: 'VyT',   title: 'Vy,Ed / Vy,pl,T,Rd  —  cisaillement réduit torsion y' },
  { key: 'ratio_VzT',  label: 'VzT',   title: 'Vz,Ed / Vz,pl,T,Rd  —  cisaillement réduit torsion z' },
  { key: 'ratio_cVN',  label: 'N+M',   title: 'Interaction N + V + M section  —  §6.2' },
  { key: 'ratio_Nb_F', label: 'Nb,F',  title: 'NEd / min(Nb,y,Rd, Nb,z,Rd)  —  flambement flexion  §6.3.1' },
  { key: 'ratio_Nb_TF',label: 'NbTF',  title: 'NEd / Nb,TF,Rd  —  flambement torsion-flexion (U seul)  §6.3.1' },
  { key: 'ratio_Mb',   label: 'Mb',    title: 'My,Ed / Mb,Rd  —  déversement  §6.3.2' },
  { key: 'ratio_MNy_b',label: 'MNy',   title: '§6.3.3 éq. 6.61  (CW)  —  interaction flambement + déversement' },
  { key: 'ratio_MNz_b',label: 'MNz',   title: '§6.3.3 éq. 6.62  (CX)  —  interaction flambement + déversement' },
]

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

function TypeBadge({ type }) {
  const p = {
    H: 'bg-blue-100   text-blue-800',
    U: 'bg-violet-100 text-violet-800',
    O: 'bg-teal-100   text-teal-800',
    X: 'bg-orange-100 text-orange-800',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-[11px] font-bold
                      ${p[type] ?? 'bg-gray-100 text-gray-600'}`}>
      {type}
    </span>
  )
}

function ClassBadge({ cls }) {
  if (cls == null) return <span className="text-gray-300">—</span>
  const p = {
    1: 'bg-green-100  text-green-800',
    2: 'bg-lime-100   text-lime-800',
    3: 'bg-yellow-100 text-yellow-800',
    4: 'bg-red-100    text-red-700 font-bold',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold
                      ${p[cls] ?? 'bg-gray-100 text-gray-600'}`}>
      {cls}
    </span>
  )
}

// ─── Composant principal ──────────────────────────────────────────────────────

export default function ResultsFormat1() {
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
        Le calcul n'a retourné aucun résultat Format 1.
      </p>
    )
  }

  // ── Ratio MAX global (sur tous les RC) ─────────────────────────────────────
  const allMaxValues = format1
    .map((rc) => rc.overall_max_ratio)
    .filter((v) => v != null)
  const globalMax = allMaxValues.length > 0 ? Math.max(...allMaxValues) : null

  return (
    <div className="space-y-5">

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

      {/* ── Tableau principal ────────────────────────────────────────────── */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="text-xs border-collapse min-w-max">

          <thead>

            {/* Ligne 1 — groupes de colonnes */}
            <tr>
              <GroupTh label="Identification"           cols={6}  first />
              <GroupTh label="Géométrie"                cols={3}  />
              <GroupTh label="Résistances section"      cols={4}  />
              <GroupTh label="Stabilité"                cols={2}  />
              <GroupTh label="Élancements"              cols={4}  />
              <GroupTh label="Efforts max"              cols={3}  />
              <GroupTh label="Ratios max  (§6.2 / §6.3)"  cols={14} />
              <GroupTh label="Synthèse"                 cols={2}  />
            </tr>

            {/* Ligne 2 — en-têtes de colonnes */}
            <tr>
              {/* Identification */}
              <Th title="Numéro du groupe RC">RC</Th>
              <Th title="Type de section  (H / U / O / X)" cls="text-center">Type</Th>
              <Th title="Désignation de la section" cls="min-w-[120px]">Section</Th>
              <Th title="Classe de section EC3  (1 à 4)" cls="text-center">Cl.</Th>
              <Th title="Désignation du matériau" cls="min-w-[80px]">Mat.</Th>
              <Th title="Limite d'élasticité (MPa)" cls="text-right">fy (MPa)</Th>
              {/* Géométrie */}
              <Th title="Hauteur de section (mm)" cls="text-right">h (mm)</Th>
              <Th title="Largeur de section (mm)" cls="text-right">b (mm)</Th>
              <Th title="Aire brute de section (cm²)" cls="text-right">A (cm²)</Th>
              {/* Résistances section */}
              <Th title="Résistance en traction  §6.2.3 (kN)" cls="text-right">Nt,Rd</Th>
              <Th title="Résistance en compression  §6.2.4 (kN)" cls="text-right">Nc,Rd</Th>
              <Th title="Résistance en flexion My  §6.2.5 (kN·m)" cls="text-right">My,c</Th>
              <Th title="Résistance en flexion Mz  §6.2.5 (kN·m)" cls="text-right">Mz,c</Th>
              {/* Stabilité */}
              <Th title="min(Nb,y,Rd ; Nb,z,Rd)  —  flambement flexion  §6.3.1 (kN)" cls="text-right">Nb,min</Th>
              <Th title="Résistance au déversement Mb,Rd  §6.3.2 (kN·m)" cls="text-right">Mb,Rd</Th>
              {/* Élancements */}
              <Th title="Élancement réduit de flambement autour de y-y" cls="text-center">λ̄y</Th>
              <Th title="Élancement réduit de flambement autour de z-z" cls="text-center">λ̄z</Th>
              <Th title="Élancement réduit de déversement" cls="text-center">λ̄LT</Th>
              <Th title="Moment critique de déversement (kN·m)" cls="text-right">Mcr (kN·m)</Th>
              {/* Efforts max */}
              <Th title="Effort normal de compression maximal (kN)" cls="text-right">NEd,c</Th>
              <Th title="Moment fléchissant My,Ed maximal (kN·m)" cls="text-right">My,Ed</Th>
              <Th title="Moment fléchissant Mz,Ed maximal (kN·m)" cls="text-right">Mz,Ed</Th>
              {/* 14 ratios */}
              {RATIOS.map(({ label, title }) => (
                <Th key={label} title={title} cls="text-center min-w-[44px]">{label}</Th>
              ))}
              {/* Synthèse */}
              <Th title="Ratio maximal global sur ce groupe RC" cls="text-center min-w-[56px]">MAX</Th>
              <Th title="Avertissements (classe 4, voilement)" cls="text-center">⚠</Th>
            </tr>
          </thead>

          <tbody>
            {format1.map((rc) => {
              const r = rc.max_ratios ?? {}

              // Nb,min = min(Nb,y,Rd, Nb,z,Rd) — null si les deux sont null
              const nbVals = [rc.Nb_y_Rd, rc.Nb_z_Rd].filter((v) => v != null)
              const nb_min = nbVals.length > 0 ? Math.min(...nbVals) : null

              const hasWarning = rc.shear_buckling_warning || rc.section_class === 4

              return (
                <tr key={rc.rc_number}
                  className="border-t border-gray-100 hover:bg-slate-50/70 transition-colors">

                  {/* Identification */}
                  <Td cls="font-semibold text-slate-800 tabular-nums">{rc.rc_number}</Td>
                  <Td cls="text-center"><TypeBadge type={rc.section_type} /></Td>
                  <Td cls="min-w-[120px]">
                    <span className="font-medium text-slate-800">{rc.designation}</span>
                    {rc.is_welded && (
                      <span className="ml-1.5 text-[10px] bg-amber-100 text-amber-700
                                       px-1 py-0.5 rounded" title="Section soudée (PRS)">
                        PRS
                      </span>
                    )}
                  </Td>
                  <Td cls="text-center"><ClassBadge cls={rc.section_class} /></Td>
                  <Td>{rc.material_designation}</Td>
                  <Td cls="text-right tabular-nums">{rc.fy}</Td>

                  {/* Géométrie */}
                  <Td cls="text-right tabular-nums">{mm_(rc.h)}</Td>
                  <Td cls="text-right tabular-nums">{mm_(rc.b)}</Td>
                  <Td cls="text-right tabular-nums">{cm2_(rc.A)}</Td>

                  {/* Résistances section */}
                  <Td cls="text-right tabular-nums">{kN(rc.Nt_Rd)}</Td>
                  <Td cls="text-right tabular-nums">{kN(rc.Nc_Rd)}</Td>
                  <Td cls="text-right tabular-nums">{kNm(rc.My_c_Rd)}</Td>
                  <Td cls="text-right tabular-nums">{kNm(rc.Mz_c_Rd)}</Td>

                  {/* Stabilité */}
                  <Td cls="text-right tabular-nums">{kN(nb_min)}</Td>
                  <Td cls="text-right tabular-nums">{kNm(rc.Mb_Rd)}</Td>

                  {/* Élancements */}
                  <Td cls="text-center tabular-nums">{nd(rc.lambda_y)}</Td>
                  <Td cls="text-center tabular-nums">{nd(rc.lambda_z)}</Td>
                  <Td cls="text-center tabular-nums">{nd(rc.lambda_LT)}</Td>
                  <Td cls="text-right tabular-nums">{kNm(rc.Mcr)}</Td>

                  {/* Efforts max */}
                  <Td cls="text-right tabular-nums">{kN(rc.NEd_c_max)}</Td>
                  <Td cls="text-right tabular-nums">{kNm(rc.My_max)}</Td>
                  <Td cls="text-right tabular-nums">{kNm(rc.Mz_max)}</Td>

                  {/* 14 ratios */}
                  {RATIOS.map(({ key }) => (
                    <RatioTd key={key} value={r[key] ?? null} />
                  ))}

                  {/* MAX global du RC */}
                  <MaxRatioTd value={rc.overall_max_ratio} />

                  {/* Avertissements */}
                  <td className="px-2 py-1.5 text-center">
                    {rc.section_class === 4 && (
                      <span className="inline-block text-[10px] bg-red-100 text-red-700
                                       px-1 py-0.5 rounded mr-0.5"
                        title="Classe 4 — vérifications partielles uniquement">
                        Cl.4
                      </span>
                    )}
                    {rc.shear_buckling_warning && (
                      <span className="text-amber-500"
                        title="Voilement par cisaillement de l'âme à vérifier">
                        ⚠
                      </span>
                    )}
                    {!hasWarning && <span className="text-gray-200">—</span>}
                  </td>

                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* ── Légende ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2.5 text-xs text-gray-500">
        <span className="font-medium">Ratios :</span>
        {[
          { bg: 'bg-green-50',   text: 'text-ratio-ok',              label: '< 0,50' },
          { bg: 'bg-yellow-50',  text: 'text-ratio-warning',         label: '0,50 – 0,90' },
          { bg: 'bg-orange-50',  text: 'text-ratio-danger font-semibold', label: '0,90 – 1,00' },
          { bg: 'bg-red-100',    text: 'text-ratio-over font-bold',  label: '> 1,00' },
          { bg: 'bg-gray-50',    text: 'text-gray-300',              label: 'N/A' },
        ].map(({ bg, text, label }) => (
          <span key={label} className={`px-2 py-0.5 rounded ${bg} ${text}`}>{label}</span>
        ))}
        <span className="text-gray-300 mx-1">|</span>
        <span className="text-gray-400">Survolez les en-têtes pour les tooltips EC3.</span>
      </div>

    </div>
  )
}
