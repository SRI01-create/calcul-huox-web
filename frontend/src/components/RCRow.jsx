// Phase 20 — Carte de configuration d'un RC (Regroupement de Calcul).
//
// Champs édités (cf. backend/app/models.py — RCConfig) :
//   section_type, designation, material_number, manual_section_class (Phase 27),
//   custom_section (Phase 32 — section personnalisée, hors catalogue),
//   L, cry, crz, buckling_curve_y, buckling_curve_z,
//   bc_steel_family/bc_u_shape/bc_u_material/bc_o_shape (guide, Phase 29 — indicatif),
//   crT (U uniquement — sans effet pour H), Lm, ltb_config, zG (H/U),
//   PTC, A_trou, Af_trou, kr
//
// Phase 31 : la fabrication (laminé/PRS soudé) n'est plus un champ éditable —
// déduite automatiquement par le backend depuis is_welded (catalogue) pour la
// désignation choisie. Le flag [PRS] (+ forme U/L, O/□, X/■●) reste affiché
// dans l'aperçu de section ci-dessous (ShapeFlags) à titre informatif.
//
// Phase 32 : section personnalisée. rc.custom_section === null → catalogue
// (comportement historique, inchangé) ; objet CustomSection → formulaire de
// saisie manuelle (CustomSectionForm ci-dessous). ClassificationControl
// continue de fonctionner en mode personnalisé (l'aperçu auto échoue
// silencieusement — pas de désignation catalogue — mais le forçage manuel
// de la classe reste pleinement utilisable). BucklingCurveGuide fonctionne
// aussi en mode personnalisé : is_welded/h/b/tf/t viennent alors du
// formulaire au lieu d'une recherche catalogue (cf. BucklingCurveGuide).
//
// Le rc_number n'est pas modifiable (identifiant stable côté store).

import React, { useEffect, useRef, useState } from 'react'
import { useStore, createDefaultCustomSection, CM2_TO_M2, CM4_TO_M4, CM3_TO_M3, CM6_TO_M6 } from '../store'
import {
  fetchSections, fetchSectionProperties, fetchSectionClassification,
  fetchBucklingCurveSuggestion, fetchCustomSectionSuggestion,
} from '../api'

// ─── Référentiels d'options ───────────────────────────────────────────────────

const SECTION_TYPES = [
  { value: 'H' },
  { value: 'U' },
  { value: 'O' },
  { value: 'X' },
]

// α (Table 6.1 EC3) rappelé pour aider au choix de la courbe.
const BUCKLING_CURVES = [
  { value: 'a0', label: 'a0 (α = 0.13)' },
  { value: 'a',  label: 'a  (α = 0.21)' },
  { value: 'b',  label: 'b  (α = 0.34)' },
  { value: 'c',  label: 'c  (α = 0.49)' },
  { value: 'd',  label: 'd  (α = 0.76)' },
]

// Options du guide de choix des courbes de flambement (Phase 29) — purement
// indicatives, cf. ec3/buckling_curve_guide.py côté backend pour la logique.
const STEEL_FAMILY_OPTIONS = [
  { value: '', label: '— choisir —' },
  { value: 's235_s420', label: 'S235 / S275 / S355 / S420' },
  { value: 's460', label: 'S460' },
  { value: 'inox', label: 'Inoxydable' },
]
const U_SHAPE_OPTIONS = [
  { value: '', label: '— choisir —' },
  { value: 'profile', label: 'Profilé U' },
  { value: 'corniere', label: 'Cornière' },
]
const U_MATERIAL_OPTIONS = [
  { value: '', label: '— choisir —' },
  { value: 'carbone', label: 'Carbone' },
  { value: 'inox', label: 'Inoxydable' },
  { value: 'inox_forme_a_froid', label: 'Inoxydable, formé à froid' },
]
const O_SHAPE_OPTIONS = [
  { value: '', label: '— choisir —' },
  { value: 'creuse_chaud', label: 'Section creuse finie à chaud' },
  { value: 'creuse_froid', label: 'Section creuse finie à froid' },
  { value: 'caisson_soude', label: 'Caisson soudé' },
  { value: 'caisson_soude_a_sup_05tf', label: 'Caisson soudé, gorge de soudure a > 0,5×tf' },
]

// Codes de configuration LTB extraits de l'Annexe F (table $CM$32:$CQ$37, Phase 12).
const LTB_CONFIGS = [
  { value: '1', label: '1 — 1/m-/D+/+  (k=1.0, kw=1.0, C1=1.000, C2=2.25)' },
  { value: '2', label: '2 — 2/m-/D+/s  (k=1.0, kw=1.0, C1=1.127, C2=1.645)' },
  { value: '3', label: '3 — 3/m-/d-    (k=1.0, kw=1.0, C1=1.000, C2=0.00)' },
  { value: '4', label: '4 — 4/M+/D+/+  (k=0.5, kw=0.5, C1=1.000, C2=2.25)' },
  { value: '5', label: '5 — 5/M+/D+/s  (k=0.5, kw=0.5, C1=1.127, C2=1.645)' },
  { value: '6', label: '6 — 6/M+/d-    (k=0.5, kw=0.5, C1=1.000, C2=0.00)' },
]

const HOLE_TYPES = [
  { value: 'P', label: 'P — Section pleine (pas de trou)' },
  { value: 'T', label: 'T — Trous catégorie A/B' },
  { value: 'C', label: 'C — Trous catégorie C' },
]

// ─── Petits champs réutilisables ──────────────────────────────────────────────

function NumField({ label, unit, value, onChange, step = 'any', min }) {
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

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="flex flex-col text-sm">
      <span className="text-gray-600 mb-1">{label}</span>
      <select
        className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  )
}

function CheckboxField({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-gray-300 text-slate-600 focus:ring-slate-400"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  )
}

/**
 * Champ numérique avec suggestion de calcul automatique (Phase 32) — même
 * principe que le guide de courbes de flambement (Phase 29) : la
 * suggestion n'est qu'une aide affichée, jamais appliquée toute seule.
 * `suggestion` est déjà formaté en texte prêt à afficher (unité comprise).
 */
function SuggestField({ label, unit, value, onChange, suggestion, onApply, step = 'any' }) {
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
        onChange={(e) => onChange(e.target.value)}
      />
      {suggestion != null && (
        <span className="mt-1 text-[11px] text-slate-500">
          Suggestion : {suggestion}{' '}
          <button
            type="button"
            className="text-slate-700 underline hover:text-slate-900"
            onClick={onApply}
          >
            Appliquer
          </button>
        </span>
      )}
    </label>
  )
}

// ─── Sélecteur de section (recherche dans le catalogue) ──────────────────────

function SectionPicker({ sectionType, designation, onChange }) {
  const [query, setQuery] = useState(designation || '')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [props, setProps] = useState(null)
  const debounceRef = useRef(null)
  const boxRef = useRef(null)

  // Si la désignation change depuis l'extérieur (ex. changement de type → reset)
  useEffect(() => {
    setQuery(designation || '')
  }, [designation, sectionType])

  // Charge un aperçu des propriétés de la désignation sélectionnée.
  useEffect(() => {
    if (!designation) {
      setProps(null)
      return
    }
    let cancelled = false
    fetchSectionProperties(sectionType, designation)
      .then((data) => { if (!cancelled) setProps(data) })
      .catch(() => { if (!cancelled) setProps(null) })
    return () => { cancelled = true }
  }, [sectionType, designation])

  // Recherche débouncée dans le catalogue à chaque frappe.
  useEffect(() => {
    if (!open) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      fetchSections(sectionType, query)
        .then((data) => setResults(data.designations))
        .catch(() => setResults([]))
    }, 250)
    return () => clearTimeout(debounceRef.current)
  }, [sectionType, query, open])

  // Ferme la liste déroulante au clic extérieur.
  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) {
        setOpen(false)
        setQuery(designation || '')
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [designation])

  const pick = (des) => {
    onChange(des)
    setQuery(des)
    setOpen(false)
  }

  return (
    <div className="flex flex-col text-sm relative" ref={boxRef}>
      <span className="text-gray-600 mb-1">Désignation</span>
      <input
        type="text"
        className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
        placeholder="Rechercher (ex. IPE, UPN 120, Tci…)"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
      />

      {open && (
        <ul className="absolute z-10 top-full mt-1 left-0 right-0 max-h-56 overflow-auto bg-white border border-gray-300 rounded shadow-lg">
          {results.length === 0 && (
            <li className="px-2 py-1.5 text-gray-400 italic">Aucun résultat</li>
          )}
          {results.map((des) => (
            <li key={des}>
              <button
                type="button"
                className={`w-full text-left px-2 py-1.5 hover:bg-slate-100 ${
                  des === designation ? 'bg-slate-50 font-medium' : ''
                }`}
                onClick={() => pick(des)}
              >
                {des}
              </button>
            </li>
          ))}
        </ul>
      )}

      {props && (
        <p className="mt-1 text-xs text-gray-500 flex items-center flex-wrap gap-x-1">
          <span>
            h={props.h}{props.b != null && ` · b=${props.b}`}
            {props.tw != null && ` · tw=${props.tw}`}
            {props.tf != null && ` · tf=${props.tf}`}
            {props.t != null && ` · t=${props.t}`}
            {' '}mm · A={(props.A * 1e4).toFixed(2)} cm²
          </span>
          <ShapeFlags sectionType={sectionType} isWelded={props.is_welded}
            isAngle={props.is_angle} isCircular={props.is_circular} />
        </p>
      )}
    </div>
  )
}

// ─── Flags de forme (Phase 31) ────────────────────────────────────────────────
// Même glyphe qu'en page "3 — Résultats" (ResultsFormat1/2.jsx) : U/L, □/O, ■/●,
// + [PRS] séparé pour is_welded — cf. leur shapeFlag() pour la logique de référence.
function ShapeFlags({ sectionType, isWelded, isAngle, isCircular }) {
  let glyph = sectionType
  let title = 'Section H (I/H)'
  if (sectionType === 'U') {
    glyph = isAngle ? 'L' : 'U'
    title = isAngle ? 'Cornière (U)' : 'Section U'
  } else if (sectionType === 'O') {
    glyph = isCircular ? 'O' : '□'
    title = isCircular ? 'Section circulaire (O)' : 'Section creuse non circulaire (O)'
  } else if (sectionType === 'X') {
    glyph = isCircular ? '●' : '■'
    title = isCircular ? 'Section pleine circulaire (X)' : 'Section pleine non circulaire (X)'
  }
  const p = {
    H: 'bg-blue-100   text-blue-800',
    U: 'bg-violet-100 text-violet-800',
    O: 'bg-teal-100   text-teal-800',
    X: 'bg-orange-100 text-orange-800',
  }
  return (
    <span className="flex items-center gap-1">
      <span className={`px-1.5 py-0.5 rounded text-[11px] font-bold ${p[sectionType] ?? 'bg-gray-100 text-gray-600'}`}
        title={title}>
        {glyph}
      </span>
      {isWelded && (
        <span className="px-1 py-0.5 rounded text-[10px] bg-amber-100 text-amber-700"
          title="Section soudée (PRS)">
          PRS
        </span>
      )}
    </span>
  )
}

// ─── Section personnalisée (hors catalogue) — Phase 32 ──────────────────────
//
// Un seul formulaire pour les 4 familles ; les champs affichés dépendent de
// sectionType et de is_angle/is_circular (mêmes conventions que le
// catalogue : pas de "b" pour une section ronde, pas de "d"/"Wpl" pour une
// cornière). Les champs marqués d'une suggestion (SuggestField) appellent
// /api/custom-section/suggest à chaque frappe (débounce 300 ms) — l'aide
// est purement indicative, jamais appliquée sans un clic explicite sur
// "Appliquer" (même principe que le guide de courbes de flambement).
//
// Unités affichées/saisies : mm pour les dimensions et pour iy/iz/ym/ys,
// cm²/cm⁴/cm³/cm⁶ pour les caractéristiques de section — converties vers
// l'unité interne du catalogue (m²/m⁴/m³/m⁶) uniquement à l'envoi à l'API
// (cf. store.js::normalizeCustomSection) ou avant un appel de suggestion.

function CustomSectionForm({ sectionType, cs, onChange, ys, onYsChange }) {
  const [suggestions, setSuggestions] = useState({})
  const debounceRef = useRef(null)

  const num = (v) => (v === '' || v === null || v === undefined ? undefined : Number(v))

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const Aval = num(cs.A), Iyval = num(cs.Iy), Izval = num(cs.Iz)
      const raw = {
        is_circular: !!cs.is_circular,
        h: num(cs.h), b: num(cs.b), tw: num(cs.tw), tf: num(cs.tf), r: num(cs.r),
        ys: num(ys),
        A: Aval !== undefined ? Aval * CM2_TO_M2 : undefined,
        Iy: Iyval !== undefined ? Iyval * CM4_TO_M4 : undefined,
        Iz: Izval !== undefined ? Izval * CM4_TO_M4 : undefined,
      }
      fetchCustomSectionSuggestion(sectionType, raw)
        .then(setSuggestions)
        .catch(() => setSuggestions({}))
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [sectionType, cs.is_circular, cs.h, cs.b, cs.tw, cs.tf, cs.r, ys, cs.A, cs.Iy, cs.Iz])

  const set = (field) => (v) => onChange({ [field]: v })

  const suggestDisplay = (field, unitConv) => {
    if (suggestions[field] == null) return null
    const v = unitConv ? suggestions[field] / unitConv : suggestions[field]
    return Math.round(v * 100) / 100
  }
  const applySuggestion = (field, unitConv) => () => {
    const v = suggestDisplay(field, unitConv)
    if (v != null) onChange({ [field]: String(v) })
  }

  const isAngle = sectionType === 'U' && cs.is_angle
  const isX = sectionType === 'X'

  return (
    <div className="border border-dashed border-slate-300 rounded-lg p-4 mt-3 bg-slate-50/50">
      <div className="flex items-center gap-4 mb-3">
        <CheckboxField label="Section soudée (PRS)" checked={cs.is_welded}
          onChange={(v) => onChange({ is_welded: v })} />
        {sectionType === 'U' && (
          <CheckboxField label="Cornière" checked={cs.is_angle}
            onChange={(v) => onChange({ is_angle: v })} />
        )}
        {(sectionType === 'O' || isX) && (
          <CheckboxField label="Section ronde" checked={cs.is_circular}
            onChange={(v) => onChange({ is_circular: v })} />
        )}
      </div>

      {/* Dimensions ------------------------------------------------------ */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <NumField label="h" unit="mm" value={cs.h} min="0" onChange={set('h')} />
        {!cs.is_circular && (
          <NumField label="b" unit="mm" value={cs.b} min="0" onChange={set('b')} />
        )}
        {sectionType === 'O' && (
          <NumField label="t" unit="mm" value={cs.t} min="0" onChange={set('t')} />
        )}
        {(sectionType === 'H' || sectionType === 'U') && (
          <>
            <NumField label="tw" unit="mm" value={cs.tw} min="0" onChange={set('tw')} />
            <NumField label="tf" unit="mm" value={cs.tf} min="0" onChange={set('tf')} />
            <NumField label="r" unit="mm" value={cs.r} min="0" onChange={set('r')} />
            {!isAngle && (
              <SuggestField label="d" unit="mm" value={cs.d} onChange={set('d')}
                suggestion={suggestDisplay('d')} onApply={applySuggestion('d')} />
            )}
          </>
        )}
      </div>

      {/* Caractéristiques de section --------------------------------------- */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-3">
        {isX ? (
          <>
            <SuggestField label="A" unit="cm²" value={cs.A} onChange={set('A')}
              suggestion={suggestDisplay('A', CM2_TO_M2)} onApply={applySuggestion('A', CM2_TO_M2)} />
            <SuggestField label="Iy" unit="cm⁴" value={cs.Iy} onChange={set('Iy')}
              suggestion={suggestDisplay('Iy', CM4_TO_M4)} onApply={applySuggestion('Iy', CM4_TO_M4)} />
            <SuggestField label="Iz" unit="cm⁴" value={cs.Iz} onChange={set('Iz')}
              suggestion={suggestDisplay('Iz', CM4_TO_M4)} onApply={applySuggestion('Iz', CM4_TO_M4)} />
            <SuggestField label="Wel,y" unit="cm³" value={cs.Wel_y} onChange={set('Wel_y')}
              suggestion={suggestDisplay('Wel_y', CM3_TO_M3)} onApply={applySuggestion('Wel_y', CM3_TO_M3)} />
            <SuggestField label="Wel,z" unit="cm³" value={cs.Wel_z} onChange={set('Wel_z')}
              suggestion={suggestDisplay('Wel_z', CM3_TO_M3)} onApply={applySuggestion('Wel_z', CM3_TO_M3)} />
            <NumField label="Wpl,y" unit="cm³" value={cs.Wpl_y} onChange={set('Wpl_y')} />
            <NumField label="Wpl,z" unit="cm³" value={cs.Wpl_z} onChange={set('Wpl_z')} />
            <NumField label="It" unit="cm⁴" value={cs.It} onChange={set('It')} />
          </>
        ) : (
          <>
            <NumField label="A" unit="cm²" value={cs.A} onChange={set('A')} />
            <NumField label="Iy" unit="cm⁴" value={cs.Iy} onChange={set('Iy')} />
            <NumField label="Iz" unit="cm⁴" value={cs.Iz} onChange={set('Iz')} />
            <NumField label="Wel,y" unit="cm³" value={cs.Wel_y} onChange={set('Wel_y')} />
            <NumField label="Wel,z" unit="cm³" value={cs.Wel_z} onChange={set('Wel_z')} />
            {!isAngle && (
              <>
                <NumField label="Wpl,y" unit="cm³" value={cs.Wpl_y} onChange={set('Wpl_y')} />
                <NumField label="Wpl,z" unit="cm³" value={cs.Wpl_z} onChange={set('Wpl_z')} />
              </>
            )}
            <NumField label="It" unit="cm⁴" value={cs.It} onChange={set('It')} />
            {(sectionType === 'H' || sectionType === 'U') && (
              <NumField label="IW" unit="cm⁶" value={cs.IW} onChange={set('IW')} />
            )}
          </>
        )}
      </div>

      {/* Aires de cisaillement + spécifique U (iy/iz/ym) ------------------- */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-3">
        <SuggestField label="Av,y" unit="cm²" value={cs.Av_y} onChange={set('Av_y')}
          suggestion={suggestDisplay('Av_y', CM2_TO_M2)} onApply={applySuggestion('Av_y', CM2_TO_M2)} />
        <SuggestField label="Av,z" unit="cm²" value={cs.Av_z} onChange={set('Av_z')}
          suggestion={suggestDisplay('Av_z', CM2_TO_M2)} onApply={applySuggestion('Av_z', CM2_TO_M2)} />
        {sectionType === 'U' && (
          <>
            <SuggestField label="iy" unit="mm" value={cs.iy} onChange={set('iy')}
              suggestion={suggestDisplay('iy')} onApply={applySuggestion('iy')} />
            <SuggestField label="iz" unit="mm" value={cs.iz} onChange={set('iz')}
              suggestion={suggestDisplay('iz')} onApply={applySuggestion('iz')} />
            <NumField label="ym" unit="mm" value={cs.ym} onChange={set('ym')} />
            <NumField label="ys" unit="mm" value={ys} onChange={onYsChange} />
          </>
        )}
      </div>

      {/* Moment sectoriel (H : Sw · U : Sw,w) — a besoin de ys ci-dessus --- */}
      {(sectionType === 'H' || sectionType === 'U') && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-3">
          {!isAngle && (
            <SuggestField label={sectionType === 'H' ? 'Sw' : 'Sw,w'} unit="cm⁴" value={cs.Sw} onChange={set('Sw')}
              suggestion={suggestDisplay('Sw', CM4_TO_M4)} onApply={applySuggestion('Sw', CM4_TO_M4)} />
          )}
        </div>
      )}

      {sectionType === 'U' && (
        <p className="mt-3 text-xs text-gray-400">
          "ys" ne sert qu'à calculer la suggestion de Sw,w, jamais utilisé par le calcul lui-même.
        </p>
      )}
    </div>
  )
}

// ─── Classe de section (auto-calculée + forçage manuel — Phase 27) ───────────
//
// La classe (1 à 4) est déterminée de façon conservative (compression pure,
// Table 5.2 EC3) à partir de la section, du matériau et de la fabrication
// uniquement — indépendante des efforts. Elle est donc calculable et
// modifiable dès cette étape, avant tout upload de fichiers.
//
// L'utilisateur peut la forcer sans aucune restriction (outil destiné à des
// ingénieurs responsables de leurs calculs) ; un warning informatif apparaît
// dans les résultats si la classe forcée diffère de l'auto-calcul.

const MANUAL_CLASS_OPTIONS = [
  { value: '', label: 'Auto' },
  { value: '1', label: '1' },
  { value: '2', label: '2' },
  { value: '3', label: '3' },
  { value: '4', label: '4' },
]

function ClassificationControl({
  sectionType, designation, fy, E, steelType,
  manualClass, onManualClassChange,
}) {
  const [autoClass, setAutoClass] = useState(null)

  useEffect(() => {
    if (!designation || !fy || !E || !steelType) {
      setAutoClass(null)
      return
    }
    let cancelled = false
    fetchSectionClassification(sectionType, designation, { fy, E, steelType })
      .then((data) => { if (!cancelled) setAutoClass(data.section_class) })
      .catch(() => { if (!cancelled) setAutoClass(null) })
    return () => { cancelled = true }
  }, [sectionType, designation, fy, E, steelType])

  const isForced = !!manualClass && manualClass !== autoClass

  return (
    <div className="flex flex-col text-sm">
      <span className="text-gray-600 mb-1">Classe de section</span>
      <div className="flex items-center gap-2">
        <select
          className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
          value={manualClass ?? ''}
          onChange={(e) => onManualClassChange(e.target.value === '' ? null : e.target.value)}
          title="Forcer la classe de section (aucune restriction — sous la responsabilité de l'ingénieur)"
        >
          {MANUAL_CLASS_OPTIONS.map((o) => (
            <option key={o.value || 'auto'} value={o.value}>{o.label}</option>
          ))}
        </select>
        {isForced ? (
          <span
            className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium whitespace-nowrap"
            title={`Classe auto-calculée (conservative) : ${autoClass ?? '?'}`}
          >
            Forcée (auto : {autoClass ?? '?'})
          </span>
        ) : (
          autoClass && <span className="text-xs text-gray-400 whitespace-nowrap">Auto : {autoClass}</span>
        )}
      </div>
    </div>
  )
}

// ─── Guide de choix des courbes de flambement (Phase 29) ─────────────────────
//
// Purement facultatif : n'écrit jamais buckling_curve_y/z sans un clic
// explicite sur "Appliquer". L'utilisateur reste entièrement libre d'ignorer
// ce guide et de renseigner les courbes directement, comme aujourd'hui. Les
// choix du guide (bc_*) sont sauvegardés sur le RC (persistance/export) mais
// ne sont jamais lus par le calcul — voir models.py.

function BucklingCurveGuide({ rc, set }) {
  const [open, setOpen] = useState(false)
  const [suggestion, setSuggestion] = useState(null)
  const [error, setError] = useState(null)

  const cs = rc.custom_section

  // Choix nécessaires et complets pour ce type de section → prêts à suggérer.
  // Phase 31 : la fabrication (laminé/PRS soudé) n'est plus un choix utilisateur
  // — elle est déduite par le backend depuis is_welded, pour H et U.
  // Phase 32 : en section personnalisée, is_welded/h/b/tf/t viennent du
  // formulaire (cs) au lieu d'une recherche catalogue.
  let ready = false
  let choices = {}
  if (rc.section_type === 'H') {
    ready = !!rc.bc_steel_family
    choices = { steelFamily: rc.bc_steel_family }
  } else if (rc.section_type === 'U') {
    ready = !!rc.bc_u_shape && !!rc.bc_u_material
    choices = { uShape: rc.bc_u_shape, uMaterial: rc.bc_u_material }
  } else if (rc.section_type === 'O') {
    const needsShape = rc.bc_steel_family && rc.bc_steel_family !== 'inox'
    ready = !!rc.bc_steel_family && (!needsShape || !!rc.bc_o_shape)
    choices = { steelFamily: rc.bc_steel_family, oShape: rc.bc_o_shape }
  } else {
    ready = true // X : aucun choix, résultat fixe
  }
  if (cs) {
    choices = {
      ...choices,
      isWelded: !!cs.is_welded,
      h: cs.h === '' ? undefined : Number(cs.h),
      b: cs.b === '' ? undefined : Number(cs.b),
      tf: cs.tf === '' ? undefined : Number(cs.tf),
      t: cs.t === '' ? undefined : Number(cs.t),
    }
  }

  useEffect(() => {
    if (!open || !ready || !rc.designation) {
      setSuggestion(null)
      setError(null)
      return
    }
    let cancelled = false
    fetchBucklingCurveSuggestion(rc.section_type, rc.designation, choices)
      .then((data) => {
        if (cancelled) return
        setSuggestion({ y: data.curve_y, z: data.curve_z })
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setSuggestion(null)
        setError(err?.response?.data?.detail || 'Suggestion indisponible.')
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, ready, rc.designation, rc.section_type, JSON.stringify(choices)])

  if (!rc.designation) return null

  return (
    <div className="col-span-2 sm:col-span-3 lg:col-span-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-slate-500 hover:text-slate-800 underline underline-offset-2"
      >
        {open ? '▾' : '▸'} Aide au choix des courbes (facultatif)
      </button>

      {open && (
        <div className="mt-2 p-3 bg-slate-50 border border-slate-200 rounded-md flex flex-wrap items-end gap-3">
          {rc.section_type === 'H' && (
            <div className="w-56">
              <SelectField label="Nuance" value={rc.bc_steel_family || ''}
                onChange={(v) => set({ bc_steel_family: v || null })} options={STEEL_FAMILY_OPTIONS} />
            </div>
          )}

          {rc.section_type === 'U' && (
            <>
              <div className="w-40">
                <SelectField label="Forme" value={rc.bc_u_shape || ''}
                  onChange={(v) => set({ bc_u_shape: v || null })} options={U_SHAPE_OPTIONS} />
              </div>
              <div className="w-56">
                <SelectField label="Matériau" value={rc.bc_u_material || ''}
                  onChange={(v) => set({ bc_u_material: v || null })} options={U_MATERIAL_OPTIONS} />
              </div>
            </>
          )}

          {rc.section_type === 'O' && (
            <>
              <div className="w-56">
                <SelectField label="Nuance" value={rc.bc_steel_family || ''}
                  onChange={(v) => set({ bc_steel_family: v || null })} options={STEEL_FAMILY_OPTIONS} />
              </div>
              {rc.bc_steel_family && rc.bc_steel_family !== 'inox' && (
                <div className="w-64">
                  <SelectField label="Forme" value={rc.bc_o_shape || ''}
                    onChange={(v) => set({ bc_o_shape: v || null })} options={O_SHAPE_OPTIONS} />
                </div>
              )}
            </>
          )}

          {rc.section_type === 'X' && (
            <div className="text-xs text-gray-500">
              Sections pleines : toujours courbe c (y-y) / c (z-z), aucun choix nécessaire.
            </div>
          )}

          {error && <div className="text-xs text-red-600 basis-full">{error}</div>}

          {suggestion && (
            <div className="flex items-center gap-2 text-sm basis-full sm:basis-auto">
              <span className="text-gray-600">
                Suggestion : <span className="font-semibold text-slate-800">{suggestion.y}</span> (y-y) /{' '}
                <span className="font-semibold text-slate-800">{suggestion.z}</span> (z-z)
              </span>
              <button
                type="button"
                onClick={() => set({ buckling_curve_y: suggestion.y, buckling_curve_z: suggestion.z })}
                className="text-xs px-2 py-1 rounded bg-slate-700 text-white hover:bg-slate-800"
              >
                Appliquer
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Section repliable ─────────────────────────────────────────────────────────

function Group({ title, children }) {
  return (
    <div className="border-t border-gray-100 pt-3 mt-3 first:border-t-0 first:pt-0 first:mt-0">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
        {title}
      </h4>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {children}
      </div>
    </div>
  )
}

// ─── Identifiant RC (éditable — Phase 28) ─────────────────────────────────────
//
// Par défaut, numérotation automatique ("1", "2"…), mais librement
// remplaçable par un identifiant texte court. Doit correspondre exactement
// (caractère pour caractère, sans espace) au token de la 2ᵉ colonne du
// fichier ELE — contrainte commune au format ELE et à la plupart des
// logiciels EF (Ansys ou autre).

function RCNumberField({ value, onChange }) {
  return (
    <label className="flex flex-col text-sm">
      <span className="text-gray-600 mb-1">Identifiant RC</span>
      <input
        type="text"
        className="w-24 border border-gray-300 rounded px-2 py-1 text-center font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400"
        value={value}
        maxLength={16}
        onChange={(e) => onChange(e.target.value.replace(/\s/g, ''))}
        title="Identifiant court (16 caractères max), sans espace — doit correspondre exactement au fichier ELE"
      />
    </label>
  )
}

// ─── Carte RC ───────────────────────────────────────────────────────────────────

export default function RCRow({ rc }) {
  const materials = useStore((s) => s.materials)
  const updateRC = useStore((s) => s.updateRC)

  const set = (patch) => updateRC(rc._uid, patch)
  const material = materials.find((m) => m.material_number === rc.material_number)

  const isHU = rc.section_type === 'H' || rc.section_type === 'U'
  const isU = rc.section_type === 'U'
  const isCustom = rc.custom_section != null
  const ltbIsPredefined = /^[1-6]$/.test(String(rc.ltb_config).trim())

  const handleSectionTypeChange = (newType) => {
    // La désignation et la section personnalisée appartiennent au type
    // précédent (champs différents selon la famille) → réinitialiser.
    set({ section_type: newType, designation: '', custom_section: null })
  }

  const toggleCustom = () => {
    if (isCustom) {
      set({ custom_section: null })
    } else {
      set({
        custom_section: createDefaultCustomSection(),
        designation: rc.designation || 'Section personnalisée',
      })
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      <div className="px-4 pt-4 pb-4">

        {/* RC et section */}
        <Group title="RC et section">
          <div className="col-span-2 sm:col-span-3 lg:col-span-4 flex flex-wrap items-end gap-3">
            <RCNumberField value={rc.rc_number} onChange={(v) => set({ rc_number: v })} />
            <div className="w-48">
              <SelectField
                label="Type de section"
                value={rc.section_type}
                onChange={handleSectionTypeChange}
                options={SECTION_TYPES.map(({ value }) => ({ value, label: value }))}
              />
            </div>
          </div>

          <div className="col-span-2 sm:col-span-3 lg:col-span-4 flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[14rem]">
              {isCustom ? (
                <label className="flex flex-col text-sm">
                  <span className="text-gray-600 mb-1">Nom (section personnalisée)</span>
                  <input
                    type="text"
                    className="border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-slate-400"
                    value={rc.designation}
                    onChange={(e) => set({ designation: e.target.value })}
                  />
                </label>
              ) : (
                <SectionPicker
                  sectionType={rc.section_type}
                  designation={rc.designation}
                  onChange={(des) => set({ designation: des })}
                />
              )}
            </div>

            <button
              type="button"
              onClick={toggleCustom}
              className="text-xs px-2 py-1.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 shrink-0"
              title={isCustom ? 'Revenir au catalogue' : 'Définir une section hors catalogue'}
            >
              {isCustom ? '↩ Catalogue' : '+ Section personnalisée'}
            </button>
          </div>
        </Group>

        {/* Section personnalisée (Phase 32) */}
        {isCustom && (
          <div className="border-t border-gray-100 pt-3 mt-3">
            <CustomSectionForm
              sectionType={rc.section_type}
              cs={rc.custom_section}
              onChange={(patch) => set({ custom_section: { ...rc.custom_section, ...patch } })}
              ys={rc.custom_section_ys}
              onYsChange={(v) => set({ custom_section_ys: v })}
            />
          </div>
        )}

        {/* Matériau et classe */}
        <Group title="Matériau et classe">
          <div className="w-56">
            <SelectField
              label="Matériau"
              value={rc.material_number}
              onChange={(v) => set({ material_number: Number(v) })}
              options={materials.map((m) => ({
                value: m.material_number,
                label: `${m.designation} (n°${m.material_number})`,
              }))}
            />
          </div>

          <div className="w-40">
            <ClassificationControl
              sectionType={rc.section_type}
              designation={rc.designation}
              fy={material?.fy}
              E={material?.E}
              steelType={material?.steel_type}
              manualClass={rc.manual_section_class}
              onManualClassChange={(v) => set({ manual_section_class: v })}
            />
          </div>
        </Group>

        {/* Flambement par flexion (toutes sections) */}
        <Group title="Flambement par flexion">
          <div className="col-span-2 sm:col-span-3 lg:col-span-4 flex flex-wrap gap-3">
            <div className="w-28">
              <NumField label="L" unit="m" value={rc.L} step="0.01" min="0.001"
                onChange={(v) => set({ L: v })} />
            </div>
          </div>

          <div className="col-span-2 sm:col-span-3 lg:col-span-4 flex flex-wrap gap-3">
            <div className="w-28">
              <NumField label="cry" value={rc.cry} step="0.05" min="0"
                onChange={(v) => set({ cry: v })} />
            </div>
            <div className="w-28">
              <NumField label="crz" value={rc.crz} step="0.05" min="0"
                onChange={(v) => set({ crz: v })} />
            </div>
          </div>

          <div className="col-span-2 sm:col-span-3 lg:col-span-4 flex flex-wrap items-start gap-3">
            <div className="w-40">
              <SelectField label="Courbe y-y" value={rc.buckling_curve_y}
                onChange={(v) => set({ buckling_curve_y: v })} options={BUCKLING_CURVES} />
            </div>
            <div className="w-40">
              <SelectField label="Courbe z-z" value={rc.buckling_curve_z}
                onChange={(v) => set({ buckling_curve_z: v })} options={BUCKLING_CURVES} />
            </div>
            <BucklingCurveGuide rc={rc} set={set} />
          </div>
        </Group>


          {/* Flambement par torsion (U uniquement — crT sans effet pour H, cf. engine_H.py) */}
          {isU && (
            <Group title="Flambement par torsion / flexion-torsion">
              <NumField label="crT" value={rc.crT} step="0.05" min="0"
                onChange={(v) => set({ crT: v })} />
            </Group>
          )}

          {/* Déversement (H/U uniquement) */}
          {isHU && (
            <Group title="Déversement">
              <NumField label="Lm" unit="m" value={rc.Lm} step="0.01" min="0.001"
                onChange={(v) => set({ Lm: v })} />
              <NumField label="zG" unit="mm" value={rc.zG} step="1"
                onChange={(v) => set({ zG: v })} />
              <div />
              <div />

              <div className="col-span-2 sm:col-span-3 lg:col-span-4 flex items-center gap-4 text-sm">
                <span className="text-gray-600">Configuration Mcr :</span>
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    checked={ltbIsPredefined}
                    onChange={() => set({ ltb_config: '3' })}
                  />
                  Configuration prédéfinie (Annexe F)
                </label>
                <label className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    checked={!ltbIsPredefined}
                    onChange={() => set({ ltb_config: '10000' })}
                  />
                  Mcr imposé (N·m)
                </label>
              </div>

              {ltbIsPredefined ? (
                <div className="col-span-2 sm:col-span-3 lg:col-span-4">
                  <SelectField label="Configuration LTB" value={rc.ltb_config}
                    onChange={(v) => set({ ltb_config: v })} options={LTB_CONFIGS} />
                </div>
              ) : (
                <NumField label="Mcr imposé" unit="N·m" value={rc.ltb_config} step="100" min="0"
                  onChange={(v) => set({ ltb_config: String(v) })} />
              )}
            </Group>
          )}

          {/* Trous / réduction de section */}
          <Group title="Réduction de section (trous)">
            <SelectField label="PTC" value={rc.PTC}
              onChange={(v) => set({ PTC: v })} options={HOLE_TYPES} />

            {rc.PTC !== 'P' && (
              <>
                <NumField label="A_trou" unit="m²" value={rc.A_trou ?? ''} step="0.0001" min="0"
                  onChange={(v) => set({ A_trou: v })} />
                <NumField label="Af_trou" unit="m²" value={rc.Af_trou ?? ''} step="0.0001" min="0"
                  onChange={(v) => set({ Af_trou: v })} />
                <NumField label="kr" value={rc.kr} step="0.05" min="0" max="1"
                  onChange={(v) => set({ kr: v })} />
              </>
            )}
          </Group>
      </div>
    </div>
  )
}
