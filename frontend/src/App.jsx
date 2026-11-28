import React, { Suspense, lazy, useState } from 'react'

import RCForm          from './components/RCForm'
import MaterialForm    from './components/MaterialForm'
import ConfigTransfer  from './components/ConfigTransfer'
import FileUpload      from './components/FileUpload'
import CalculateButton from './components/CalculateButton'
// Refonte page « 3 — Résultats » : en-tête commun · fiches par RC · synthèse · détail
import ResultsOverview  from './components/ResultsOverview'
import ResultsRCSheets  from './components/ResultsRCSheets'
import ResultsFormat1   from './components/ResultsFormat1'
import ResultsFormat2   from './components/ResultsFormat2'
// Onglet « Présentation & guide » : chargé à la demande (n'alourdit pas l'outil de calcul)
const PresentationPage = lazy(() => import('./components/PresentationPage'))
// Onglet « Validation et cas test » : idem, chargé à la demande
const ValidationPage = lazy(() => import('./components/ValidationPage'))

const STEPS = [
  { id: 'config',  label: '1 — Configuration RC & Matériaux' },
  { id: 'import',  label: '2 — Import fichiers & Calcul'     },
  { id: 'results', label: '3 — Résultats'                    },
  // Hors étapes de calcul : non numéroté, à la suite de l'onglet 3
  { id: 'guide',   label: 'Présentation & guide' },
  { id: 'validation', label: 'Validation et cas test' },
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
      <nav className="bg-white border-b border-gray-200 px-6 py-2 flex gap-6 overflow-x-auto">
        {STEPS.map((step) => (
          <button
            key={step.id}
            onClick={() => setActiveStep(step.id)}
            className={`text-sm font-medium py-2 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
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
                Import des fichiers
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
            <ResultsOverview />
            <ResultsRCSheets />
            <ResultsFormat1 />
            <ResultsFormat2 />
          </div>
        )}
        {activeStep === 'guide' && (
          <Suspense fallback={<p className="text-sm text-gray-400 text-center py-16">Chargement…</p>}>
            <PresentationPage />
          </Suspense>
        )}
        {activeStep === 'validation' && (
          <Suspense fallback={<p className="text-sm text-gray-400 text-center py-16">Chargement…</p>}>
            <ValidationPage />
          </Suspense>
        )}
      </main>

      {/* Pied de page */}
      <footer className="bg-white border-t border-gray-200 px-6 py-3 text-xs text-gray-400 text-center">
        Calcul HUOX · Sem Riazi ·{' '}
        <a
          href="https://www.linkedin.com/in/sem-riazi"
          target="_blank"
          rel="noopener noreferrer"
          className="underline text-slate-500 hover:text-slate-700"
        >
          Contact : LinkedIn
        </a>
      </footer>
    </div>
  )
}
