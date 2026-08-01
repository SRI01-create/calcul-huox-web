import React, { useState } from 'react'

import RCForm          from './components/RCForm'
import MaterialForm    from './components/MaterialForm'
import ConfigTransfer  from './components/ConfigTransfer'
import FileUpload      from './components/FileUpload'
import CalculateButton from './components/CalculateButton'
// Phase 22 : ResultsFormat1 activé
import ResultsFormat1  from './components/ResultsFormat1'
// Phase 23 : ResultsFormat2 activé
import ResultsFormat2  from './components/ResultsFormat2'

const STEPS = [
  { id: 'config',  label: '1 — Configuration RC & Matériaux' },
  { id: 'import',  label: '2 — Import fichiers & Calcul'     },
  { id: 'results', label: '3 — Résultats'                    },
]

export default function App() {
  const [activeStep, setActiveStep] = useState('config')

  return (
    <div className="min-h-screen flex flex-col">

      {/* En-tête */}
      <header className="bg-slate-800 text-white px-6 py-4 shadow">
        <h1 className="text-xl font-bold tracking-wide">Calcul HUOX</h1>
        <p className="text-slate-400 text-sm mt-0.5">
          Post-traitement EC3 · NF EN 1993-1-1 / 1-4
        </p>
      </header>

      {/* Navigation par étapes */}
      <nav className="bg-white border-b border-gray-200 px-6 py-2 flex gap-6">
        {STEPS.map((step) => (
          <button
            key={step.id}
            onClick={() => setActiveStep(step.id)}
            className={`text-sm font-medium py-2 border-b-2 transition-colors ${
              activeStep === step.id
                ? 'border-slate-700 text-slate-800'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {step.label}
          </button>
        ))}
      </nav>

      {/* Contenu principal */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        {activeStep === 'config' && (
          <div>
            <ConfigTransfer />
            <MaterialForm />
            <RCForm />
          </div>
        )}
        {activeStep === 'import' && (
          <div className="max-w-2xl mx-auto space-y-8">
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-4">
                Import des fichiers Ansys
              </h2>
              <FileUpload />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-4">
                Lancement du calcul
              </h2>
              <CalculateButton onSuccess={() => setActiveStep('results')} />
            </div>
          </div>
        )}
        {activeStep === 'results' && (
          <div>
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-slate-800 mb-1">
                Synthèse par groupe RC
              </h2>
              <p className="text-sm text-gray-500">
                Format 1 — Un résultat par groupe RC. Les 14 ratios sont les valeurs
                maximales sur l'ensemble des éléments et des cas de charge du groupe.
              </p>
            </div>
            <ResultsFormat1 />
            <ResultsFormat2 />
          </div>
        )}
      </main>

      {/* Pied de page */}
      <footer className="bg-white border-t border-gray-200 px-6 py-3 text-xs text-gray-400 text-center">
        Calcul HUOX · Sem Riazi · NF EN 1993-1-1 / NF EN 1993-1-4
      </footer>
    </div>
  )
}
