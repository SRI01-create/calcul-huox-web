// Phase 20 — Carte de configuration d'un RC (Regroupement de Calcul).
//
// Champs édités (cf. backend/app/models.py — RCConfig) :
//   section_type, designation, material_number,
//   L, cry, crz, buckling_curve_y, buckling_curve_z,
//   crT (H/U), Lm, ltb_config, fabrication, zG (H/U),
//   PTC, A_trou, Af_trou, kr
//
// Le rc_number n'est pas modifiable (identifiant stable côté store).

import React, { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { fetchSections, fetchSectionProperties } from '../api'

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
        <p className="mt-1 text-xs text-gray-500">
          h={props.h}{props.b != null && ` · b=${props.b}`}
          {props.tw != null && ` · tw=${props.tw}`}
          {props.tf != null && ` · tf=${props.tf}`}
          {props.t != null && ` · t=${props.t}`}
          {' '}mm · A={(props.A * 1e4).toFixed(2)} cm²
          {props.is_welded && ' · PRS soudé'}
          {props.is_angle && ' · cornière'}
          {props.is_circular && ' · circulaire'}
        </p>
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

// ─── Carte RC ───────────────────────────────────────────────────────────────────

export default function RCRow({ rc }) {
  const materials = useStore((s) => s.materials)
  const updateRC = useStore((s) => s.updateRC)
  const removeRC = useStore((s) => s.removeRC)
  const [expanded, setExpanded] = useState(true)

  const num = rc.rc_number
  const set = (patch) => updateRC(num, patch)

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
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-700 text-white text-sm font-semibold shrink-0">
          {num}
        </span>

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
          onClick={() => removeRC(num)}
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
          </Group>

          {/* Flambement par torsion (H/U uniquement) */}
          {isHU && (
            <Group title="Flambement par torsion / flexion-torsion — §6.3.1.4">
              <NumField label="crT" value={rc.crT} step="0.05" min="0"
                onChange={(v) => set({ crT: v })} />
              {!isU && (
                <div className="col-span-3 flex items-center text-xs text-gray-400">
                  Flambement par flexion-torsion non vérifié pour les sections H
                  (bi-symétriques) — crT requis pour la cohérence du modèle.
                </div>
              )}
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
