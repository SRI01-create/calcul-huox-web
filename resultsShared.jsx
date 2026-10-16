// Refonte page « 3 — Résultats » — éléments communs aux 3 blocs :
//   • ResultsRCSheets.jsx  (fiches par RC)
//   • ResultsFormat1.jsx   (synthèse des résultats par RC)
//   • ResultsFormat2.jsx   (détail par élément × cas de charge)
//
// Regroupe les helpers de formatage, le code couleur des ratios, les badges
// (type de section, classe, [PRS] [froid] [perso]) et les cellules de tableau
// qui étaient auparavant dupliqués dans ResultsFormat1/2.

import React from 'react'

// ─── Helpers de formatage ─────────────────────────────────────────────────────
// Convention : valeur null (non applicable / hors portée) → « — ».

// Efforts et résistances : N → kN, N·m → kN·m (1 décimale, comme avant)
export const kN  = (v) => v != null ? (v / 1e3).toFixed(1) : '—'
export const kNm = (v) => v != null ? (v / 1e3).toFixed(1) : '—'

// Valeur adimensionnelle à 3 décimales (λ̄)
export const nd = (v) => v != null ? v.toFixed(3) : '—'

// Valeur à n chiffres significatifs, après conversion d'unité (facteur).
// Évite de perdre l'information sur les petites valeurs (ex. Iw = 0,09 cm⁶,
// tf = 4,2 mm) tout en restant lisible sur les grandes (ex. Iy = 92 080 cm⁴).
export function sig(v, factor = 1, digits = 5) {
  if (v == null) return '—'
  return String(Number((v * factor).toPrecision(digits)))
}

// Facteurs de conversion unités internes (m) → unités affichées (cm)
export const TO_CM2 = 1e4    // m²  → cm²
export const TO_CM3 = 1e6    // m³  → cm³
export const TO_CM4 = 1e8    // m⁴  → cm⁴
export const TO_CM6 = 1e12   // m⁶  → cm⁶

// ─── Code couleur ratio ───────────────────────────────────────────────────────

export function ratioClasses(v) {
  if (v == null) return 'bg-gray-50 text-gray-300'
  if (v > 1.0)  return 'bg-red-100   text-ratio-over   font-bold'
  if (v >= 0.9) return 'bg-orange-50 text-ratio-danger font-semibold'
  if (v >= 0.5) return 'bg-yellow-50 text-ratio-warning'
  return               'bg-green-50  text-ratio-ok'
}

export function RatioTd({ value }) {
  return (
    <td className={`px-1.5 py-1 text-center text-xs tabular-nums ${ratioClasses(value)}`}>
      {value != null ? value.toFixed(3) : '—'}
    </td>
  )
}

export function MaxRatioTd({ value, size = 'text-sm' }) {
  return (
    <td className={`px-2 py-1 text-center ${size} font-bold tabular-nums ${ratioClasses(value)}`}>
      {value != null ? value.toFixed(3) : '—'}
    </td>
  )
}

// ─── Les 14 ratios (AllRatios) — intitulés de la refonte ──────────────────────
// Intitulés : ceux du descriptif « Evolution de la page résultats ».
// « N+M » devient « NVTM » ; les autres noms sont inchangés ou sans virgule.

export const RATIOS = [
  { key: 'ratio_N',     label: 'N',    title: 'NEd / Nt,Rd ou NEd / Nc,Rd  —  §6.2.3/4' },
  { key: 'ratio_Vy',    label: 'Vy',   title: 'Vy,Ed / Vpl,y,Rd  —  §6.2.6' },
  { key: 'ratio_Vz',    label: 'Vz',   title: 'Vz,Ed / Vpl,z,Rd  —  §6.2.6' },
  { key: 'ratio_T',     label: 'T',    title: 'τ / τ_Rd  —  torsion  §6.2.7' },
  { key: 'ratio_cy',    label: 'cy',   title: 'My,Ed / My,c,Rd  —  flexion section  §6.2.5' },
  { key: 'ratio_cz',    label: 'cz',   title: 'Mz,Ed / Mz,c,Rd  —  flexion section  §6.2.5' },
  { key: 'ratio_VyT',   label: 'VyT',  title: 'Vy,Ed / Vy,pl,T,Rd  —  cisaillement réduit torsion y' },
  { key: 'ratio_VzT',   label: 'VzT',  title: 'Vz,Ed / Vz,pl,T,Rd  —  cisaillement réduit torsion z' },
  { key: 'ratio_cVN',   label: 'NVTM', title: 'Interaction N + V + M section  —  §6.2' },
  { key: 'ratio_Nb_F',  label: 'NbF',  title: 'NEd / min(Nb,y,Rd, Nb,z,Rd)  —  flambement flexion  §6.3.1' },
  { key: 'ratio_Nb_TF', label: 'NbTF', title: 'NEd / Nb,TF,Rd  —  flambement torsion-flexion (U)  §6.3.1' },
  { key: 'ratio_Mb',    label: 'Mb',   title: 'My,Ed / Mb,Rd  —  déversement  §6.3.2' },
  { key: 'ratio_MNy_b', label: 'MNy',  title: '§6.3.3 éq. 6.61  —  interaction flambement + déversement' },
  { key: 'ratio_MNz_b', label: 'MNz',  title: '§6.3.3 éq. 6.62  —  interaction flambement + déversement' },
]

// ─── Sous-composants de tableau ───────────────────────────────────────────────

export function GroupTh({ label, cols, first = false }) {
  return (
    <th colSpan={cols}
      className={`px-3 py-1.5 text-left text-[11px] font-semibold tracking-wide
                  text-white bg-slate-700
                  ${first ? '' : 'border-l border-slate-500'}`}>
      {label}
    </th>
  )
}

export function Th({ children, title, cls = '' }) {
  return (
    <th title={title}
      className={`px-2 py-1.5 whitespace-nowrap text-left text-[11px] font-semibold
                  text-slate-600 bg-slate-100 border-b border-slate-200 ${cls}`}>
      {children}
    </th>
  )
}

export function Td({ children, cls = '' }) {
  return (
    <td className={`px-2 py-1.5 whitespace-nowrap text-xs text-slate-700 ${cls}`}>
      {children}
    </td>
  )
}

// Tests « oui / non / n.a. » (Phase 36). null = n/a.
export function yesNoNA(v) {
  if (v == null) return <span className="text-gray-300">n/a</span>
  return v
    ? <span className="text-ratio-ok font-medium">oui</span>
    : <span className="text-slate-500">non</span>
}

// ─── Badges ───────────────────────────────────────────────────────────────────

// Glyphe selon le type ET la forme réelle de la section (Phase 31) :
//   H → H · U → U (profilé) | L (cornière)
//   O → □ (non circulaire) | O (circulaire)
//   X → ■ (non circulaire) | ● (circulaire)
export function shapeFlag(type, isAngle, isCircular) {
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

export function TypeBadge({ type, isAngle, isCircular }) {
  const p = {
    H: 'bg-blue-100   text-blue-800',
    U: 'bg-violet-100 text-violet-800',
    O: 'bg-teal-100   text-teal-800',
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

export function ClassBadge({ cls }) {
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

// Désignation + badges [PRS] [froid] [perso].
// `item` = RCSummary ou ElementLCResult (mêmes noms de champs).
export function SectionLabel({ item }) {
  return (
    <>
      <span className="font-medium text-slate-800">{item.designation}</span>
      {item.is_welded && (
        <span className="ml-1.5 text-[10px] bg-amber-100 text-amber-700
                         px-1 py-0.5 rounded" title="Section soudée (PRS)">
          PRS
        </span>
      )}
      {item.fabrication === 'F' && (
        <span className="ml-1.5 text-[10px] bg-cyan-100 text-cyan-700
                         px-1 py-0.5 rounded" title="Section formée à froid">
          froid
        </span>
      )}
      {item.is_custom && (
        <span className="ml-1.5 text-[10px] bg-pink-100 text-pink-700
                         px-1 py-0.5 rounded" title="Section personnalisée (hors catalogue)">
          perso
        </span>
      )}
    </>
  )
}

// ─── Légende des ratios (identique dans la synthèse et le détail) ─────────────

export function RatioLegend({ cls = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-2.5 text-xs text-gray-500 ${cls}`}>
      <span className="font-medium">Ratios :</span>
      {[
        { bg: 'bg-green-50',  text: 'text-ratio-ok',                  label: '< 0,50' },
        { bg: 'bg-yellow-50', text: 'text-ratio-warning',             label: '0,50 – 0,90' },
        { bg: 'bg-orange-50', text: 'text-ratio-danger font-semibold', label: '0,90 – 1,00' },
        { bg: 'bg-red-100',   text: 'text-ratio-over font-bold',      label: '> 1,00' },
        { bg: 'bg-gray-50',   text: 'text-gray-300',                  label: 'N/A' },
      ].map(({ bg, text, label }) => (
        <span key={label} className={`px-2 py-0.5 rounded ${bg} ${text}`}>{label}</span>
      ))}
      <span className="text-gray-300 mx-1">|</span>
      <span className="text-gray-400">Survolez les en-têtes pour les tooltips EC3.</span>
    </div>
  )
}
