// Refonte page « 3 — Résultats » — bloc 2 : synthèse des résultats par RC.
//
// Remplace l'ancien tableau « Synthèse par groupe RC » (géométrie, résistances,
// élancements… désormais dans les fiches par RC). Une ligne par RC, 4 groupes :
//   Identification · Dispenses · Efforts et moments maximaux · Ratios maximaux
// + la colonne ⚠ (alertes) conservée en dernière colonne.
//
// Source : store.result.format1 (liste de RCSummary). Les efforts et ratios
// sont les maxima sur l'ensemble des éléments et cas de charge du RC.
// Valeur null (vérification hors-portée) → cellule grisée « — ».
// Unités : efforts en kN, moments en kN·m.

import React from 'react'
import { useStore } from '../store'
import {
  kN, kNm, RATIOS, RatioTd, MaxRatioTd, GroupTh, Th, Td,
  yesNoNA, TypeBadge, ClassBadge, SectionLabel, RatioLegend,
} from './resultsShared'
import { ANCHORS } from './ResultsOverview'

// Efforts et moments maximaux : intitulés du descriptif, unité dans le titre.
const EFFORTS = [
  { label: 'NtE', unit: 'kN',   key: 'NEd_t_max', fmt: kN,  title: 'Effort normal de traction maximal NEd,t' },
  { label: 'NcE', unit: 'kN',   key: 'NEd_c_max', fmt: kN,  title: 'Effort normal de compression maximal NEd,c' },
  { label: 'VyE', unit: 'kN',   key: 'Vy_max',    fmt: kN,  title: 'Effort tranchant maximal Vy,Ed' },
  { label: 'VzE', unit: 'kN',   key: 'Vz_max',    fmt: kN,  title: 'Effort tranchant maximal Vz,Ed' },
  { label: 'TE',  unit: 'kN·m', key: 'T_max',     fmt: kNm, title: 'Moment de torsion maximal TEd' },
  { label: 'MyE', unit: 'kN·m', key: 'My_max',    fmt: kNm, title: 'Moment fléchissant maximal My,Ed' },
  { label: 'MzE', unit: 'kN·m', key: 'Mz_max',    fmt: kNm, title: 'Moment fléchissant maximal Mz,Ed' },
]

export default function ResultsFormat1() {
  const result = useStore((s) => s.result)
  const format1 = result?.format1
  if (!format1 || format1.length === 0) return null

  return (
    <section id={ANCHORS.summary} className="space-y-4 mt-10 pt-8 border-t border-gray-200 scroll-mt-4">

      <div>
        <h2 className="text-lg font-semibold text-slate-800">
          Synthèse des résultats par RC
        </h2>
        <p className="text-sm text-gray-500 mt-0.5">
          Efforts et ratios maximaux sur l'ensemble des éléments et des cas de charge de chaque groupe RC.
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="text-xs border-collapse min-w-max">

          <thead>
            {/* Ligne 1 — groupes de colonnes */}
            <tr>
              <GroupTh label="Identification"              cols={5} first />
              <GroupTh label="Dispenses"                   cols={2} />
              <GroupTh label="Efforts et moments maximaux" cols={EFFORTS.length} />
              <GroupTh label="Ratios maximaux"             cols={RATIOS.length + 1} />
              <GroupTh label=""                            cols={1} />
            </tr>

            {/* Ligne 2 — en-têtes de colonnes */}
            <tr>
              {/* Identification */}
              <Th title="Numéro du groupe RC">RC</Th>
              <Th title="Type de section (flag de forme)" cls="text-center">Type</Th>
              <Th title="Désignation de la section — badges [PRS] [froid] [perso]" cls="min-w-[120px]">Section</Th>
              <Th title="Classe de section EC3 (1 à 4)" cls="text-center">Cl.</Th>
              <Th title="Désignation du matériau" cls="min-w-[80px]">Mat.</Th>
              {/* Dispenses */}
              <Th title="Pour les âmes dépourvues de raidisseurs intermédiaires, possibilité de s'abstenir de la vérification au voilement par cisaillement" cls="text-center">Voil.</Th>
              <Th title="Possibilité d'ignorer les trous dans la semelle tendue en flexion" cls="text-center">Trous</Th>
              {/* Efforts et moments maximaux */}
              {EFFORTS.map(({ label, unit, title }) => (
                <Th key={label} title={`${title} (${unit})`} cls="text-right">
                  {label} <span className="font-normal text-slate-400">({unit})</span>
                </Th>
              ))}
              {/* Ratios maximaux */}
              {RATIOS.map(({ label, title }) => (
                <Th key={label} title={title} cls="text-center min-w-[44px]">{label}</Th>
              ))}
              <Th title="Ratio maximal global sur ce groupe RC" cls="text-center min-w-[56px]">MAX</Th>
              {/* Alertes */}
              <Th title="Avertissements (classe 4, voilement)" cls="text-center">⚠</Th>
            </tr>
          </thead>

          <tbody>
            {format1.map((rc) => {
              const r = rc.max_ratios ?? {}
              const hasWarning = rc.shear_buckling_warning || rc.section_class === '4'

              return (
                <tr key={rc.rc_number}
                  className="border-t border-gray-100 hover:bg-slate-50/70 transition-colors">

                  {/* Identification */}
                  <Td cls="font-semibold text-slate-800">{rc.rc_number}</Td>
                  <Td cls="text-center">
                    <TypeBadge type={rc.section_type} isAngle={rc.is_angle} isCircular={rc.is_circular} />
                  </Td>
                  <Td cls="min-w-[120px]"><SectionLabel item={rc} /></Td>
                  <Td cls="text-center"><ClassBadge cls={rc.section_class} /></Td>
                  <Td>{rc.material_designation}</Td>

                  {/* Dispenses */}
                  <Td cls="text-center">{yesNoNA(rc.shear_buckling_ignored)}</Td>
                  <Td cls="text-center">{yesNoNA(rc.holes_ignored)}</Td>

                  {/* Efforts et moments maximaux */}
                  {EFFORTS.map(({ key, fmt }) => (
                    <Td key={key} cls="text-right tabular-nums">{fmt(rc[key])}</Td>
                  ))}

                  {/* Ratios maximaux */}
                  {RATIOS.map(({ key }) => (
                    <RatioTd key={key} value={r[key] ?? null} />
                  ))}
                  <MaxRatioTd value={rc.overall_max_ratio} />

                  {/* Alertes */}
                  <td className="px-2 py-1.5 text-center">
                    {rc.section_class === '4' && (
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

      <RatioLegend />

    </section>
  )
}
