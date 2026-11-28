// Onglet « Présentation & guide ».
//
// Affiche, dans son intégralité, le document de présentation de l'outil.
// Le contenu est dans src/content/presentation/*.html (un fichier par partie,
// éditable à la main sur GitHub) ; les images sont dans public/presentation/.
// La mise en page (sommaire, numérotation, renvois, tableaux) est dans DocPage.jsx.

import React from 'react'
import DocPage from './DocPage'

import part1 from '../content/presentation/1-presentation.html?raw'
import part2 from '../content/presentation/2-guide-utilisation.html?raw'
import part3 from '../content/presentation/3-caracterisation.html?raw'

const PARTS = [part1, part2, part3]

export default function PresentationPage() {
  return <DocPage parts={PARTS} numbered />
}
