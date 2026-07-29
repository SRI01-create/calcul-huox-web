// Phase 21 — Import des fichiers Ansys (étape 2).
//
// Deux zones de dépôt :
//   1. Fichier ELE    — un seul fichier (liste éléments → numéro RC)
//   2. Fichiers CdC   — un ou plusieurs fichiers de cas de charge Ansys
//                       (le nom du CdC est dérivé du nom de fichier sans
//                       extension : "LC80.txt" → cas "LC80")
//
// Interactions :
//   • Drag-and-drop sur chaque zone
//   • Clic → sélection par le sélecteur de fichiers natif
//   • LC : ajout incrémental (plusieurs dépôts successifs autorisés)
//   • LC : bouton ✕ par fichier pour le retirer individuellement
//   • Double-clic sur un fichier LC existant → ne le remplace pas
//     (on filtre les doublons de nom au dépôt)
//
// Persistance : aucune — les File ne sont pas sérialisables.
// L'état est dans le store Zustand (Phase 19 : setEleFile, addLcFiles, removeLcFile).

import React, { useRef, useState } from 'react'
import { useStore } from '../store'

// ─── Zone de dépôt générique ─────────────────────────────────────────────────

function DropZone({ label, hint, accept, multiple, onDrop, children }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const handleDragOver = (e) => { e.preventDefault(); setDragging(true) }
  const handleDragLeave = () => setDragging(false)
  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const files = [...e.dataTransfer.files]
    if (files.length > 0) onDrop(files)
  }
  const handleChange = (e) => {
    const files = [...e.target.files]
    if (files.length > 0) onDrop(files)
    e.target.value = ''   // reset pour permettre un re-sélection du même fichier
  }

  return (
    <div>
      <p className="text-sm font-medium text-gray-700 mb-1">{label}</p>
      {hint && <p className="text-xs text-gray-400 mb-2">{hint}</p>}

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg px-4 py-5 text-center cursor-pointer transition-colors ${
          dragging
            ? 'border-slate-500 bg-slate-50'
            : 'border-gray-300 hover:border-slate-400 hover:bg-gray-50'
        }`}
      >
        <svg className="mx-auto mb-2 h-8 w-8 text-gray-400" fill="none"
          viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm text-gray-500">
          Glisser-déposer ou{' '}
          <span className="text-slate-700 font-medium underline">parcourir</span>
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={handleChange}
        />
      </div>

      {children}
    </div>
  )
}

// ─── FileUpload ───────────────────────────────────────────────────────────────

export default function FileUpload() {
  const eleFile     = useStore((s) => s.eleFile)
  const lcFiles     = useStore((s) => s.lcFiles)
  const setEleFile  = useStore((s) => s.setEleFile)
  const addLcFiles  = useStore((s) => s.addLcFiles)
  const removeLcFile= useStore((s) => s.removeLcFile)

  // Dépôt ELE : un seul fichier, on prend le premier.
  const handleEle = (files) => setEleFile(files[0])

  // Dépôt LC : ajout incrémental, doublons filtrés par nom.
  const handleLc = (files) => {
    const existing = new Set(lcFiles.map((f) => f.name))
    const fresh = files.filter((f) => !existing.has(f.name))
    if (fresh.length > 0) addLcFiles(fresh)
  }

  // Nom de CdC dérivé du nom de fichier (sans extension).
  const lcName = (filename) => filename.replace(/\.[^.]+$/, '')

  return (
    <div className="space-y-6">

      {/* ── Fichier ELE ─────────────────────────────────────────────────── */}
      <DropZone
        label="Fichier ELE — liste des éléments"
        hint="Un fichier texte à deux colonnes : numéro d'élément  numéro RC (une ligne par élément)."
        accept=".txt,.dat,.lis,.csv"
        multiple={false}
        onDrop={handleEle}
      >
        {eleFile && (
          <div className="mt-3 flex items-center justify-between bg-green-50 border border-green-200 rounded px-3 py-2">
            <div className="flex items-center gap-2 text-sm text-green-800">
              <svg className="h-4 w-4 text-green-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="font-medium">{eleFile.name}</span>
              <span className="text-green-600">({(eleFile.size / 1024).toFixed(1)} Ko)</span>
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setEleFile(null) }}
              className="text-green-600 hover:text-red-600 text-lg leading-none px-1"
              title="Retirer ce fichier"
            >
              ×
            </button>
          </div>
        )}
      </DropZone>

      {/* ── Fichiers de cas de charge ─────────────────────────────────── */}
      <DropZone
        label="Fichiers de cas de charge (CdC)"
        hint={
          'Un fichier par cas de charge. Le nom du CdC est dérivé du nom de fichier ' +
          '(ex. "LC80.txt" → cas "LC80"). Plusieurs dépôts successifs sont possibles.'
        }
        accept=".txt,.dat,.lis,.rst"
        multiple={true}
        onDrop={handleLc}
      >
        {lcFiles.length > 0 && (
          <div className="mt-3 space-y-1" onClick={(e) => e.stopPropagation()}>
            <p className="text-xs text-gray-500 mb-2">
              {lcFiles.length} fichier{lcFiles.length > 1 ? 's' : ''} — cliquer sur ✕ pour retirer
            </p>
            {lcFiles.map((f) => (
              <div
                key={f.name}
                className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded px-3 py-1.5"
              >
                <div className="flex items-center gap-2 text-sm text-slate-700 min-w-0">
                  <svg className="h-4 w-4 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                  <span className="truncate font-medium">{f.name}</span>
                  <span className="text-slate-400 shrink-0">→ cas "{lcName(f.name)}"</span>
                </div>
                <button
                  type="button"
                  onClick={() => removeLcFile(f.name)}
                  className="text-slate-400 hover:text-red-600 text-lg leading-none px-1 shrink-0"
                  title={`Retirer ${f.name}`}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </DropZone>

    </div>
  )
}
