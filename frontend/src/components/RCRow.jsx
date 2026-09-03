// Phase 20 — Carte de configuration d'un RC (Regroupement de Calcul).
//
// Champs édités (cf. backend/app/models.py — RCConfig) :
//   section_type, designation, material_number, manual_section_class (Phase 27),
//   L, cry, crz, buckling_curve_y, buckling_curve_z,
//   bc_steel_family/bc_u_shape/bc_u_material/bc_o_shape (guide, Phase 29 — indicatif),
//   crT (U uniquement — sans effet pour H), Lm, ltb_config, fabrication, zG (H/U),
//   PTC, A_trou, Af_trou, kr
//
// Le rc_number n'est pas modifiable (identifiant stable côté store).

import React, { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { fetchSections, fetchSectionProperties, fetchSectionClassification, fetchBucklingCurveSuggestion } from '../api'

// ─── Référentiels d'options ───────────────────────────────────────────────────

const SECTION_TYPES = [
  { value: 'H', label: 'H — Profilés I/H (IPE, HEA, HEB, PRS…)' },
  { value: 'U', label: 'U — Profilés U et cornières (UPN, UPE, L…)' },
  { value: 'O', label: 'O — Tubes creux (Tca, Tre, Tci)' },
  { value: 'X', label: 'X — Sections pleines (Pca, Pre, Pci)' },
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
  sectionType, designation, fy, E, steelType, fabrication,
  manualClass, onManualClassChange,
}) {
  const [autoClass, setAutoClass] = useState(null)

  useEffect(() => {
    if (!designation || !fy || !E || !steelType) {
      setAutoClass(null)
      return
    }
    let cancelled = false
    fetchSectionClassification(sectionType, designation, { fy, E, steelType, fabrication })
      .then((data) => { if (!cancelled) setAutoClass(data.section_class) })
      .catch(() => { if (!cancelled) setAutoClass(null) })
    return () => { cancelled = true }
  }, [sectionType, designation, fy, E, steelType, fabrication])

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

  // Choix nécessaires et complets pour ce type de section → prêts à suggérer.
  let ready = false
  let choices = {}
  if (rc.section_type === 'H') {
    ready = !!rc.bc_steel_family
    choices = { steelFamily: rc.bc_steel_family, fabrication: rc.fabrication }
  } else if (rc.section_type === 'U') {
    const needsFabrication = rc.bc_u_material === 'inox'
    ready = !!rc.bc_u_shape && !!rc.bc_u_material && (!needsFabrication || !!rc.fabrication)
    choices = { uShape: rc.bc_u_shape, uMaterial: rc.bc_u_material, fabrication: rc.fabrication }
  } else if (rc.section_type === 'O') {
    const needsShape = rc.bc_steel_family && rc.bc_steel_family !== 'inox'
    ready = !!rc.bc_steel_family && (!needsShape || !!rc.bc_o_shape)
    choices = { steelFamily: rc.bc_steel_family, oShape: rc.bc_o_shape }
  } else {
    ready = true // X : aucun choix, résultat fixe
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
            <>
              <div className="w-56">
                <SelectField label="Nuance" value={rc.bc_steel_family || ''}
                  onChange={(v) => set({ bc_steel_family: v || null })} options={STEEL_FAMILY_OPTIONS} />
              </div>
              <div className="text-xs text-gray-500 pb-2">
                Fabrication : <span className="font-medium">{rc.fabrication === 'S' ? 'PRS (soudé)' : 'Laminé'}</span>
                {' '}(cf. groupe « Déversement » ci-dessous)
              </div>
            </>
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
              {rc.bc_u_material === 'inox' && (
                <div className="text-xs text-gray-500 pb-2">
                  Fabrication : <span className="font-medium">{rc.fabrication === 'S' ? 'PRS (soudé)' : 'Laminé'}</span>
                  {' '}(cf. groupe « Déversement » ci-dessous)
                </div>
              )}
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
  const removeRC = useStore((s) => s.removeRC)
  const [expanded, setExpanded] = useState(true)

  const set = (patch) => updateRC(rc._uid, patch)
  const material = materials.find((m) => m.material_number === rc.material_number)

  const isHU = rc.section_type === 'H' || rc.section_type === 'U'
  const isU = rc.section_type === 'U'
  const ltbIsPredefined = /^[1-6]$/.test(String(rc.ltb_config).trim())

  const handleSectionTypeChange = (newType) => {
    // La désignation appartient au catalogue de l'ancien type → réinitialiser.
    set({ section_type: newType, designation: '' })
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      {/* En-tête ------------------------------------------------------------ */}
      <div className="flex flex-wrap items-center gap-3 p-4">
        <RCNumberField value={rc.rc_number} onChange={(v) => set({ rc_number: v })} />

        <div className="w-48 shrink-0">
          <SelectField
            label="Type de section"
            value={rc.section_type}
            onChange={handleSectionTypeChange}
            options={SECTION_TYPES.map(({ value, label }) => ({ value, label: value }))}
          />
        </div>

        <div className="flex-1 min-w-[14rem]">
          <SectionPicker
            sectionType={rc.section_type}
            designation={rc.designation}
            onChange={(des) => set({ designation: des })}
          />
        </div>

        <div className="w-56 shrink-0">
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

        <div className="w-40 shrink-0">
          <ClassificationControl
            sectionType={rc.section_type}
            designation={rc.designation}
            fy={material?.fy}
            E={material?.E}
            steelType={material?.steel_type}
            fabrication={rc.fabrication}
            manualClass={rc.manual_section_class}
            onManualClassChange={(v) => set({ manual_section_class: v })}
          />
        </div>

        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="text-gray-400 hover:text-slate-700 text-sm self-end pb-1"
          title={expanded ? 'Réduire' : 'Développer les paramètres'}
        >
          {expanded ? '▾ Paramètres' : '▸ Paramètres'}
        </button>

        <button
          type="button"
          onClick={() => removeRC(rc._uid)}
          className="text-gray-400 hover:text-red-600 text-lg leading-none self-end pb-1.5"
          title="Supprimer ce RC"
        >
          ×
        </button>
      </div>

      {/* Type de section sélectionné — légende */}
      <div className="px-4 -mt-2 pb-1 text-xs text-gray-400">
        {SECTION_TYPES.find((t) => t.value === rc.section_type)?.label}
      </div>

      {/* Détails -------------------------------------------------------------- */}
      {expanded && (
        <div className="px-4 pb-4">

          {/* Flambement par flexion (toutes sections) */}
          <Group title="Flambement par flexion — §6.3.1">
            <NumField label="L" unit="m" value={rc.L} step="0.01" min="0.001"
              onChange={(v) => set({ L: v })} />
            <NumField label="cry" value={rc.cry} step="0.05" min="0"
              onChange={(v) => set({ cry: v })} />
            <NumField label="crz" value={rc.crz} step="0.05" min="0"
              onChange={(v) => set({ crz: v })} />
            <div />
            <SelectField label="Courbe y-y" value={rc.buckling_curve_y}
              onChange={(v) => set({ buckling_curve_y: v })} options={BUCKLING_CURVES} />
            <SelectField label="Courbe z-z" value={rc.buckling_curve_z}
              onChange={(v) => set({ buckling_curve_z: v })} options={BUCKLING_CURVES} />
            <BucklingCurveGuide rc={rc} set={set} />
          </Group>

          {/* Flambement par torsion (U uniquement — crT sans effet pour H, cf. engine_H.py) */}
          {isU && (
            <Group title="Flambement par torsion / flexion-torsion — §6.3.1.4">
              <NumField label="crT" value={rc.crT} step="0.05" min="0"
                onChange={(v) => set({ crT: v })} />
            </Group>
          )}

          {/* Déversement (H/U uniquement) */}
          {isHU && (
            <Group title="Déversement — §6.3.2, Annexe F">
              <NumField label="Lm" unit="m" value={rc.Lm} step="0.01" min="0.001"
                onChange={(v) => set({ Lm: v })} />
              <SelectField label="Fabrication" value={rc.fabrication}
                onChange={(v) => set({ fabrication: v })}
                options={[
                  { value: 'L', label: 'L — Laminé / formé à froid' },
                  { value: 'S', label: 'S — PRS soudé' },
                ]} />
              <NumField label="zG" unit="mm" value={rc.zG} step="1"
                onChange={(v) => set({ zG: v })} />
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
      )}
    </div>
  )
}
