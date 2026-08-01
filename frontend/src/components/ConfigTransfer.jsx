// Phase 26 — Export / import de la configuration RC & Matériaux.
//
// Permet de sauvegarder la configuration courante (matériaux + RC) dans un
// fichier JSON téléchargeable, puis de la recharger ultérieurement — utile
// pour réutiliser une configuration type d'un projet à l'autre sans tout
// ressaisir.

import React, { useRef, useState } from 'react'
import { useStore } from '../store'

function downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function defaultFilename() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}h${pad(d.getMinutes())}`
  return `calcul-huox-config_${stamp}.json`
}

export default function ConfigTransfer() {
  const exportConfig = useStore((s) => s.exportConfig)
  const importConfig = useStore((s) => s.importConfig)
  const inputRef = useRef(null)
  const [feedback, setFeedback] = useState(null) // { type: 'success' | 'error', message }

  const handleExport = () => {
    downloadJSON(exportConfig(), defaultFilename())
    setFeedback({ type: 'success', message: 'Configuration exportée.' })
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // permet de re-sélectionner le même fichier plus tard
    if (!file) return

    const reader = new FileReader()
    reader.onload = () => {
      let data
      try {
        data = JSON.parse(reader.result)
      } catch {
        setFeedback({ type: 'error', message: "Fichier invalide : ce n'est pas du JSON valide." })
        return
      }
      const res = importConfig(data)
      setFeedback(
        res.ok
          ? { type: 'success', message: 'Configuration chargée.' }
          : { type: 'error', message: res.error }
      )
    }
    reader.onerror = () => {
      setFeedback({ type: 'error', message: 'Impossible de lire le fichier.' })
    }
    reader.readAsText(file)
  }

  return (
    <div className="flex items-center gap-3 mb-6">
      <button
        type="button"
        onClick={handleExport}
        className="text-sm bg-white border border-gray-300 text-slate-700 rounded px-3 py-1.5 hover:bg-gray-50 transition-colors"
      >
        Exporter la configuration
      </button>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="text-sm bg-white border border-gray-300 text-slate-700 rounded px-3 py-1.5 hover:bg-gray-50 transition-colors"
      >
        Charger une configuration
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".json,.txt"
        className="hidden"
        onChange={handleFileChange}
      />

      {feedback && (
        <span className={`text-sm ${feedback.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
          {feedback.message}
        </span>
      )}
    </div>
  )
}
