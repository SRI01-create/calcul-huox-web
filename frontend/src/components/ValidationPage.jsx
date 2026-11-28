// Onglet « Validation et cas test ».
//
// Reprend le document « Calcul HUOX — cas test » : introduction, tableau des
// clauses couvertes, 11 cas test avec leurs tableaux de résultats comparés.
// Le contenu est dans src/content/validation/*.html (éditable sur GitHub) ; les
// images sont dans public/validation/. Les titres portent déjà leur numéro
// (« Cas test n°1 ») : pas de numérotation automatique.
//
// Couleurs des tableaux comparés (classes définies dans validation.css) :
//   .cmp-eq  « = »  vert    ·  .cmp-warn  « < » ou « > »  orange  ·  .cmp-bad  rouge
//   p.approved  mention « APPROUVÉ » en vert.
// La couleur de chaque case vient du Word, case par case (un « < » peut être
// orange ou rouge) : en modifier une = changer sa classe dans le HTML.
//
// Chaque cas test est un bloc <section class="cas"> : titre h2, puis une grille
// .cas-grid (colonne .cas-desc = description, colonne .cas-res = tableau comparé,
// côte à côte sur écran assez large, empilées sinon), puis .cas-concl = conclusion.
// Pour un nouveau cas, recopier ce schéma (mise en page dans validation.css).
//
// Les deux boutons (téléchargement, PDF) sont insérés à l'emplacement
// <div data-slot="validation-actions"> de l'introduction (ValidationActions.jsx).

import React from 'react'
import DocPage from './DocPage'
import ValidationActions from './ValidationActions'
import './validation.css'

import part1 from '../content/validation/1-introduction.html?raw'
import part2 from '../content/validation/2-cas-test-1-a-6.html?raw'
import part3 from '../content/validation/3-cas-test-7-a-11.html?raw'

const PARTS = [part1, part2, part3]
const SLOTS = { 'validation-actions': <ValidationActions /> }

export default function ValidationPage() {
  return <DocPage parts={PARTS} numbered={false} slots={SLOTS} openFirst />
}
