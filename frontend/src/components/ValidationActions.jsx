// Les deux boutons de l'onglet « Validation et cas test » :
//   1. télécharger les 3 fichiers Calcul HUOX (un seul zip) ;
//   2. consulter les PDF des contre-calculs (liste des 11 cas → aperçu Google Drive,
//      dans un nouvel onglet, sans option de téléchargement côté Drive).

import React, { useEffect, useRef, useState } from 'react'
import { CONTRE_CALCULS } from '../content/validation/contre-calculs'

// Zip placé dans frontend/public/validation/ (contient les 3 fichiers du cas test).
const ZIP_URL = '/validation/Calcul-HUOX_fichiers-cas-test.zip'

export default function ValidationActions() {
  const [open, setOpen] = useState(false)
  const boxRef = useRef(null)

  // Ferme la liste : clic en dehors ou touche Échap.
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false) }
    const onKey  = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="val-actions" ref={boxRef}>
      <a className="val-btn val-btn-primary" href={ZIP_URL} download>
        <span aria-hidden="true">⭳</span> Télécharger les fichiers Calcul HUOX
      </a>

      <div className="val-menu">
        <button
          type="button"
          className="val-btn"
          aria-expanded={open}
          aria-haspopup="true"
          onClick={() => setOpen((o) => !o)}
        >
          <span aria-hidden="true">▤</span> Consulter les contre-calculs (PDF)
          <span aria-hidden="true" className="val-caret">{open ? '▴' : '▾'}</span>
        </button>

        {open && (
          <ul className="val-list" role="list">
            {CONTRE_CALCULS.map(({ cas, url }) => (
              <li key={cas}>
                <a href={url} target="_blank" rel="noopener noreferrer" onClick={() => setOpen(false)}>
                  Cas test n°{cas}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
