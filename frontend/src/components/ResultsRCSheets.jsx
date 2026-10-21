// Refonte page « 3 — Résultats » — bloc 1 : fiches par RC.
//
// Pour chaque RC, une carte dépliable contenant 9 petits tableaux (une ligne
// de données chacun) : Identification · Géométrie · Caractéristiques · Trou ·
// Matériau · Instabilités de flambement · Instabilités de déversement (H, U) ·
// Résistances primaires de la section · Résistances aux instabilités.
//
// Les colonnes de chaque tableau s'adaptent à la famille de section, selon le
// descriptif « Evolution de la page résultats ». Règle générale : sauf
// exclusion explicite, une cornière fait partie des U.
//
// Source : store.result.format1 (liste de RCSummary). Affichage uniquement :
// aucune valeur n'est recalculée ici (seules des conversions d'unités).
//
// Unités affichées : mm · m (L, Lm) · cm² · cm³ · cm⁴ · cm⁶ · MPa · kN · kN·m.

import React, { useEffect, useState } from 'react'
import { useStore } from '../store'
import {
  kN, kNm, nd, sig, TO_CM2, TO_CM3, TO_CM4, TO_CM6,
  ratioClasses, Th, Td, TypeBadge, ClassBadge, SectionLabel,
} from './resultsShared'
import { ANCHORS } from './ResultsOverview'

// ─── Prédicats de famille ─────────────────────────────────────────────────────

const isH      = (rc) => rc.section_type === 'H'
const isU      = (rc) => rc.section_type === 'U'
const isO      = (rc) => rc.section_type === 'O'
const isHU     = (rc) => isH(rc) || isU(rc)
const isAngle  = (rc) => isU(rc) && rc.is_angle           // cornière (⊂ U)
const isCirc   = (rc) => (isO(rc) || rc.section_type === 'X') && rc.is_circular
const noAngle  = (rc) => !isAngle(rc)
const holed    = (rc) => rc.PTC !== 'P'
const isInox   = (rc) => rc.steel_type === 'inox'

// ─── Définition d'une colonne ─────────────────────────────────────────────────
// label  : intitulé tel qu'écrit dans le descriptif
// unit   : unité, ajoutée entre parenthèses dans le titre de colonne
// show   : (rc) => bool — la colonne n'apparaît que si la section est concernée
// render : (rc) => contenu de la cellule

const col = (label, unit, title, show, render, align = 'text-right') =>
  ({ label, unit, title, show, render, align })

const ALL = () => true

// ─── Libellés ─────────────────────────────────────────────────────────────────

const PTC_LABEL = { P: 'Pas de trou', T: 'Cat. A/B', C: 'Cat. C' }
const FAB_LABEL = { L: 'Laminé', S: 'PRS', F: 'Formé à froid' }
const LTB_CFG   = ['1', '2', '3', '4', '5', '6']

// ─── Les 9 tableaux ───────────────────────────────────────────────────────────

const TABLES = [
  {
    key: 'identification',
    title: 'Identification',
    columns: [
      col('RC', null, 'Numéro du groupe RC', ALL, (rc) => rc.rc_number, 'text-left'),
      col('Type', null, 'Type de section (flag de forme)', ALL,
        (rc) => <TypeBadge type={rc.section_type} isAngle={rc.is_angle} isCircular={rc.is_circular} />,
        'text-center'),
      col('Section', null, 'Désignation de la section — badges [PRS] [froid] [perso]', ALL,
        (rc) => <SectionLabel item={rc} />, 'text-left'),
      col('Cl.', null, 'Classe de section EC3 (1 à 4)', ALL,
        (rc) => <ClassBadge cls={rc.section_class} />, 'text-center'),
    ],
  },
  {
    key: 'geometrie',
    title: 'Géométrie',
    columns: [
      col('l', 'mm', 'Longueur des ailes (cornière égale)', isAngle, (rc) => sig(rc.h, 1, 4)),
      col('h', 'mm', 'Hauteur de section', (rc) => !isCirc(rc) && noAngle(rc), (rc) => sig(rc.h, 1, 4)),
      col('b', 'mm', 'Largeur de section', (rc) => !isCirc(rc) && noAngle(rc), (rc) => sig(rc.b, 1, 4)),
      col('Ø', 'mm', 'Diamètre (tube rond, section pleine ronde)', isCirc, (rc) => sig(rc.h, 1, 4)),
      col('t', 'mm', 'Épaisseur (tube)', isO, (rc) => sig(rc.t, 1, 4)),
      col('t', 'mm', 'Épaisseur des ailes (cornière égale)', isAngle, (rc) => sig(rc.tw, 1, 4)),
      col('tw', 'mm', "Épaisseur d'âme", (rc) => isHU(rc) && noAngle(rc), (rc) => sig(rc.tw, 1, 4)),
      col('tf', 'mm', 'Épaisseur de semelle', (rc) => isHU(rc) && noAngle(rc), (rc) => sig(rc.tf, 1, 4)),
      col('r', 'mm', 'Rayon de raccordement', isHU, (rc) => sig(rc.r, 1, 4)),
      col('d', 'mm', "Hauteur droite d'âme", (rc) => isHU(rc) && noAngle(rc), (rc) => sig(rc.d, 1, 4)),
      col('iy', 'mm', 'Rayon de giration autour de y-y', isU, (rc) => sig(rc.iy, 1, 4)),
      col('iz', 'mm', 'Rayon de giration autour de z-z', isU, (rc) => sig(rc.iz, 1, 4)),
      col('ym', 'mm', 'Distance du centre de gravité au centre de cisaillement', isU, (rc) => sig(rc.ym, 1, 4)),
      col('ys', 'mm', 'Position du centre de cisaillement', (rc) => isU(rc) && noAngle(rc), (rc) => sig(rc.ys, 1, 4)),
    ],
  },
  {
    key: 'caracteristiques',
    title: 'Caractéristiques',
    columns: [
      col('A', 'cm²', 'Aire brute de la section', ALL, (rc) => sig(rc.A, TO_CM2)),
      col('Avy', 'cm²', 'Aire de cisaillement selon y', ALL, (rc) => sig(rc.Av_y, TO_CM2)),
      col('Avz', 'cm²', 'Aire de cisaillement selon z', ALL, (rc) => sig(rc.Av_z, TO_CM2)),
      col('Iy', 'cm⁴', "Moment d'inertie de flexion autour de y-y", ALL, (rc) => sig(rc.Iy, TO_CM4)),
      col('Wely', 'cm³', 'Module de flexion élastique autour de y-y', ALL, (rc) => sig(rc.Wel_y, TO_CM3)),
      col('Wply', 'cm³', 'Module de flexion plastique autour de y-y', noAngle, (rc) => sig(rc.Wpl_y, TO_CM3)),
      col('Iz', 'cm⁴', "Moment d'inertie de flexion autour de z-z", ALL, (rc) => sig(rc.Iz, TO_CM4)),
      col('Welz', 'cm³', 'Module de flexion élastique autour de z-z', ALL, (rc) => sig(rc.Wel_z, TO_CM3)),
      col('Wplz', 'cm³', 'Module de flexion plastique autour de z-z', noAngle, (rc) => sig(rc.Wpl_z, TO_CM3)),
      col('It', 'cm⁴', 'Constante de torsion de Saint-Venant', ALL, (rc) => sig(rc.It, TO_CM4)),
      col('Iw', 'cm⁶', 'Constante de gauchissement', isHU, (rc) => sig(rc.Iw, TO_CM6)),
      col('Sω', 'cm⁴', 'Moment statique de gauchissement (H)', isH, (rc) => sig(rc.Sw, TO_CM4)),
      col('Sωw', 'cm⁴', 'Moment statique de gauchissement (U)', (rc) => isU(rc) && noAngle(rc), (rc) => sig(rc.Sw_w, TO_CM4)),
      col('Sw,max', 'cm⁴', 'Moment statique de gauchissement maximal (cornière égale)', isAngle, (rc) => sig(rc.Sw_w, TO_CM4)),
    ],
  },
  {
    key: 'trou',
    title: 'Trou',
    columns: [
      col('PTC', null, "Pas de trou, ou trou avec catégorie d'assemblage A/B ou C", ALL,
        (rc) => PTC_LABEL[rc.PTC] ?? rc.PTC, 'text-left'),
      col('Anet', 'cm²', 'Aire nette de la section', holed, (rc) => sig(rc.Anet, TO_CM2)),
      col('Atrou', 'cm²', 'Aire totale des trous', holed, (rc) => sig(rc.A_trou, TO_CM2)),
      col('Afnet', 'cm²', 'Aire nette de la semelle tendue',
        (rc) => holed(rc) && isHU(rc) && noAngle(rc), (rc) => sig(rc.Af_net, TO_CM2)),
      col('Aftrou', 'cm²', 'Aire des trous dans la semelle',
        (rc) => holed(rc) && isHU(rc) && noAngle(rc), (rc) => sig(rc.Af_trou, TO_CM2)),
      col('Kr', null, 'Coefficient de participation à la traction (inox)',
        (rc) => holed(rc) && isInox(rc), (rc) => sig(rc.kr, 1, 3)),
    ],
  },
  {
    key: 'materiau',
    title: 'Matériau',
    columns: [
      col('Mat.', null, 'Désignation du matériau', ALL, (rc) => rc.material_designation, 'text-left'),
      col('Type', null, 'Type de matériau (carbone ou inox)', ALL, (rc) => rc.steel_type, 'text-left'),
      col('fy', 'MPa', "Limite d'élasticité", ALL, (rc) => sig(rc.fy, 1, 6)),
      col('fu', 'MPa', 'Résistance ultime en traction', ALL, (rc) => sig(rc.fu, 1, 6)),
      col('E', 'MPa', 'Module de Young', ALL, (rc) => sig(rc.E, 1, 6)),
      col('G', 'MPa', 'Module de cisaillement', ALL, (rc) => sig(rc.G, 1, 6)),
      col('γM0', null, 'Coefficient partiel γM0', ALL, (rc) => sig(rc.gamma_M0, 1, 3)),
      col('γM1', null, 'Coefficient partiel γM1', ALL, (rc) => sig(rc.gamma_M1, 1, 3)),
      col('γM2', null, 'Coefficient partiel γM2', ALL, (rc) => sig(rc.gamma_M2, 1, 3)),
    ],
  },
  {
    key: 'flambement',
    title: 'Instabilités de flambement',
    columns: [
      col('L', 'm', 'Longueur de barre', ALL, (rc) => sig(rc.L, 1, 5)),
      col('cry', null, 'Coefficient de longueur de flambement autour de y-y', ALL, (rc) => sig(rc.cry, 1, 4)),
      col('crz', null, 'Coefficient de longueur de flambement autour de z-z', ALL, (rc) => sig(rc.crz, 1, 4)),
      col('crT', null, 'Coefficient de longueur de flambement par torsion', isU, (rc) => sig(rc.crT, 1, 4)),
      col('Courbe de flambement y-y', null, 'Courbe de flambement autour de y-y', ALL,
        (rc) => rc.buckling_curve_y, 'text-center'),
      col('Courbe de flambement z-z', null, 'Courbe de flambement autour de z-z', ALL,
        (rc) => rc.buckling_curve_z, 'text-center'),
      col('λ', null, 'Élancement réduit maximal : λ = max(λ̄y ; λ̄z)', ALL,
        (rc) => nd(rc.lambda_max), 'text-center'),
    ],
  },
  {
    key: 'deversement',
    title: 'Instabilités de déversement',
    columns: [
      col('Lm', 'm', 'Longueur entre maintiens latéraux', isHU, (rc) => sig(rc.Lm, 1, 5)),
      col('Fabrication', null, 'Mode de fabrication : laminé, PRS ou formé à froid', isHU,
        (rc) => FAB_LABEL[rc.fabrication] ?? '—', 'text-left'),
      col('zG', 'mm', 'Distance entre le point d\'application de la charge et le centre de cisaillement',
        isHU, (rc) => sig(rc.zG, 1, 5)),
      col('Cfg. Mcr', null, 'Configuration de calcul de Mcr (1 à 6), ou « imposé » si Mcr a été saisi', isHU,
        (rc) => LTB_CFG.includes(rc.ltb_config) ? rc.ltb_config : 'imposé', 'text-center'),
      col('λLT', null, 'Élancement réduit de déversement', isHU, (rc) => nd(rc.lambda_LT), 'text-center'),
      col('λLT,0', null, 'Plateau de l\'élancement réduit de déversement', isHU,
        (rc) => nd(rc.lambda_LT0), 'text-center'),
    ],
  },
  {
    key: 'primaires',
    title: 'Résistances primaires de la section transversale',
    columns: [
      col('Nt', 'kN', 'Résistance en traction Nt,Rd — §6.2.3', ALL, (rc) => kN(rc.Nt_Rd)),
      col('Nc', 'kN', 'Résistance en compression Nc,Rd — §6.2.4', ALL, (rc) => kN(rc.Nc_Rd)),
      col('My,c', 'kN·m', 'Résistance en flexion My,c,Rd — §6.2.5', ALL, (rc) => kNm(rc.My_c_Rd)),
      col('Mz,c', 'kN·m', 'Résistance en flexion Mz,c,Rd — §6.2.5', ALL, (rc) => kNm(rc.Mz_c_Rd)),
      col('Vy,pl', 'kN', 'Résistance plastique au cisaillement Vpl,y,Rd — §6.2.6', ALL, (rc) => kN(rc.Vy_pl_Rd)),
      col('Vz,pl', 'kN', 'Résistance plastique au cisaillement Vpl,z,Rd — §6.2.6', ALL, (rc) => kN(rc.Vz_pl_Rd)),
    ],
  },
  {
    key: 'instabilites',
    title: 'Résistances aux instabilités de flambement et de déversement',
    columns: [
      col('Ncr', 'kN', 'Charge critique de flambement par flexion Ncr,min = min(Ncr,y ; Ncr,z)', ALL, (rc) => kN(rc.Ncr_min)),
      col('NcrT', 'kN', 'Charge critique de flambement par torsion', isU, (rc) => kN(rc.Ncr_T)),
      col('NcrTF', 'kN', 'Charge critique de flambement par flexion-torsion', isU, (rc) => kN(rc.Ncr_TF)),
      col('Nby', 'kN', 'Résistance au flambement autour de y-y — Nb,y,Rd §6.3.1', ALL, (rc) => kN(rc.Nb_y_Rd)),
      col('Nbz', 'kN', 'Résistance au flambement autour de z-z — Nb,z,Rd §6.3.1', ALL, (rc) => kN(rc.Nb_z_Rd)),
      col('NbTF', 'kN', 'Résistance au flambement par flexion-torsion — Nb,TF,Rd §6.3.1', isU, (rc) => kN(rc.Nb_TF_Rd)),
      col('Mcr', 'kN·m', 'Moment critique de déversement (imposé ou calculé)', isHU, (rc) => kNm(rc.Mcr)),
      col('Mb', 'kN·m', 'Résistance au déversement Mb,Rd — §6.3.2', isHU, (rc) => kNm(rc.Mb_Rd)),
    ],
  },
]

// ─── Un tableau (une ligne de données) ────────────────────────────────────────

function MiniTable({ table, rc }) {
  const cols = table.columns.filter((c) => c.show(rc))
  if (cols.length === 0) return null
  return (
    <div>
      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-1">
        {table.title}
      </p>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="text-xs border-collapse min-w-max w-full">
          <thead>
            <tr>
              {cols.map((c) => (
                <Th key={c.label} title={c.title} cls={c.align}>
                  {c.label}
                  {c.unit && <span className="font-normal text-slate-400"> ({c.unit})</span>}
                </Th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-gray-100">
              {cols.map((c) => (
                <Td key={c.label} cls={`${c.align} tabular-nums`}>{c.render(rc)}</Td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Une fiche RC (carte dépliable) ───────────────────────────────────────────

function RCSheet({ rc, open, onToggle }) {
  const maxR = rc.overall_max_ratio
  return (
    <div className="border border-gray-200 rounded-lg bg-white shadow-sm">
      <button type="button" onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left
                   hover:bg-slate-50 transition-colors rounded-lg">
        <span className="text-slate-400 text-xs w-3">{open ? '▾' : '▸'}</span>
        <span className="font-semibold text-slate-800 text-sm">RC {rc.rc_number}</span>
        <TypeBadge type={rc.section_type} isAngle={rc.is_angle} isCircular={rc.is_circular} />
        <span className="text-sm"><SectionLabel item={rc} /></span>
        <span className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          MAX
          <span className={`px-2 py-0.5 rounded font-bold tabular-nums ${ratioClasses(maxR)}`}>
            {maxR != null ? maxR.toFixed(3) : '—'}
          </span>
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 space-y-3 border-t border-gray-100">
          {TABLES.map((t) => <MiniTable key={t.key} table={t} rc={rc} />)}
        </div>
      )}
    </div>
  )
}

// ─── Composant principal ──────────────────────────────────────────────────────

// Au-delà de ce nombre de RC, les fiches sont repliées par défaut.
const AUTO_OPEN_MAX = 5

export default function ResultsRCSheets() {
  const result = useStore((s) => s.result)
  // Écarts par rapport à l'état par défaut : { [rc_number]: true | false }
  const [overrides, setOverrides] = useState({})

  // Nouveau calcul → on repart de l'état par défaut
  useEffect(() => { setOverrides({}) }, [result])

  const format1 = result?.format1
  if (!format1 || format1.length === 0) return null

  const defaultOpen = format1.length <= AUTO_OPEN_MAX
  const isOpen = (rcNum) => overrides[rcNum] ?? defaultOpen

  const setAll = (value) =>
    setOverrides(Object.fromEntries(format1.map((rc) => [rc.rc_number, value])))

  return (
    <section id={ANCHORS.sheets} className="space-y-3 scroll-mt-4">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <h2 className="text-lg font-semibold text-slate-800">Fiches par RC</h2>
        <div className="flex gap-2 text-xs">
          <button type="button" onClick={() => setAll(true)}
            className="px-2.5 py-1 rounded border border-slate-300 bg-white
                       text-slate-600 hover:border-slate-500 transition-colors">
            Tout déplier
          </button>
          <button type="button" onClick={() => setAll(false)}
            className="px-2.5 py-1 rounded border border-slate-300 bg-white
                       text-slate-600 hover:border-slate-500 transition-colors">
            Tout replier
          </button>
        </div>
      </div>

      {format1.map((rc) => (
        <RCSheet key={rc.rc_number} rc={rc} open={isOpen(rc.rc_number)}
          onToggle={() => setOverrides((o) => ({ ...o, [rc.rc_number]: !isOpen(rc.rc_number) }))} />
      ))}
    </section>
  )
}
