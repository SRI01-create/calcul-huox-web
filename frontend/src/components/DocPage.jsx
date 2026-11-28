// Page de document générique : contenu HTML + sommaire en arborescence à gauche.
// Utilisée par les onglets « Présentation & guide » (PresentationPage.jsx) et
// « Validation et cas test » (ValidationPage.jsx).
//
// Tout le reste est automatique, à partir des titres <h1>/<h2>/<h3> :
//   · numérotation (1, 1.1, 1.1.1) ;
//   · sommaire en arborescence dans la marge de gauche (replié au départ,
//     la branche de la section en cours s'ouvre pendant la lecture) ;
//   · renvois <a class="xref" data-xref="id-du-titre">§…</a> : le numéro
//     affiché est recalculé (si on ajoute une section, il se met à jour) ;
//   · tableaux placés dans un conteneur à défilement horizontal.
//
// Pour ajouter une section : ajouter un <h2 id="pg-…">Titre</h2> dans le bon fichier.

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import './presentation.css'

const TALL_TABLE_ROWS = 25   // au-delà : hauteur limitée + en-tête collant
const ACTIVE_OFFSET   = 120  // px depuis le haut de la fenêtre

// ── Construction du document : numérotation, sommaire, renvois, tableaux ────
export function buildDocument(parts, numbered = true) {
  const doc = new DOMParser().parseFromString(
    `<body>${parts.join('\n')}</body>`, 'text/html',
  )
  const counters = [0, 0, 0]
  const flat = []        // tous les titres, dans l'ordre
  const roots = []       // arborescence
  const lastAt = [null, null, null]
  const numById = {}

  doc.body.querySelectorAll('h1, h2, h3').forEach((h) => {
    const level = Number(h.tagName[1])
    counters[level - 1] += 1
    for (let i = level; i < 3; i++) counters[i] = 0
    const num = counters.slice(0, level).join('.')
    if (!h.id) h.id = `pg-${num.replace(/\./g, '-')}`
    const title = h.textContent.trim()

    // numéro devant le titre (désactivable : certains documents numérotent eux-mêmes leurs titres)
    if (numbered) {
      const span = doc.createElement('span')
      span.className = 'doc-num'
      span.textContent = num
      if (h.firstChild && h.firstChild.nodeType === 3) {
        h.firstChild.textContent = h.firstChild.textContent.replace(/^\s+/, '')
      }
      h.insertBefore(span, h.firstChild)
    }

    const node = { id: h.id, num, title, level, children: [], parent: null }
    numById[h.id] = num
    flat.push(node)
    if (level === 1) roots.push(node)
    else {
      const parent = lastAt[level - 2]
      if (parent) { node.parent = parent.id; parent.children.push(node) }
      else roots.push(node)
    }
    lastAt[level - 1] = node
    for (let i = level; i < 3; i++) lastAt[i] = null
  })

  // renvois « §x.y » : numéro recalculé d'après le titre visé
  doc.body.querySelectorAll('a[data-xref]').forEach((a) => {
    const n = numById[a.getAttribute('data-xref')]
    if (n) a.textContent = `§${n}`
  })

  // tableaux : conteneur à défilement horizontal
  doc.body.querySelectorAll('table').forEach((t) => {
    const wrap = doc.createElement('div')
    wrap.className = 'tbl-wrap' + (t.rows.length > TALL_TABLE_ROWS ? ' tall' : '')
    t.replaceWith(wrap)
    wrap.appendChild(t)
  })

  return { html: doc.body.innerHTML, roots, flat }
}

// ── Utilitaires ─────────────────────────────────────────────────────────────
function ancestorsOf(id, byId) {
  const out = []
  let cur = byId[id]?.parent
  while (cur) { out.push(cur); cur = byId[cur]?.parent }
  return out
}

function goTo(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// ── Sommaire (arborescence) ─────────────────────────────────────────────────
function TocNode({ node, open, activeId, onToggle, onGo, numbered }) {
  const hasKids = node.children.length > 0
  const isOpen = open.has(node.id)
  const isActive = activeId === node.id
  const pad = node.level === 1 ? 'pl-1' : node.level === 2 ? 'pl-5' : 'pl-9'

  return (
    <li>
      <div className={`flex items-start gap-1 rounded ${pad} ${isActive ? 'bg-slate-100' : ''}`}>
        {hasKids ? (
          <button
            type="button"
            onClick={() => onToggle(node.id)}
            aria-expanded={isOpen}
            aria-label={`${isOpen ? 'Replier' : 'Déplier'} ${numbered ? node.num + ' ' : ''}${node.title}`}
            className="mt-1.5 w-4 shrink-0 text-xs text-slate-400 hover:text-slate-700"
          >
            {isOpen ? '▾' : '▸'}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <button
          type="button"
          data-toc-id={node.id}
          aria-current={isActive ? 'true' : undefined}
          onClick={() => onGo(node)}
          className={`flex-1 text-left py-1 pr-2 text-[13px] leading-snug hover:text-slate-900 ${
            node.level === 1 ? 'font-semibold' : ''
          } ${isActive ? 'text-slate-900 font-medium' : 'text-slate-600'}`}
        >
          {numbered && <span className="text-slate-400 mr-1.5 tabular-nums">{node.num}</span>}
          {node.title}
        </button>
      </div>
      {hasKids && isOpen && (
        <ul>
          {node.children.map((c) => (
            <TocNode key={c.id} node={c} open={open} activeId={activeId}
              onToggle={onToggle} onGo={onGo} numbered={numbered} />
          ))}
        </ul>
      )}
    </li>
  )
}

function Toc({ roots, open, activeId, onToggle, onGo, numbered }) {
  return (
    <nav aria-label="Sommaire">
      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide px-1 mb-2">
        Sommaire
      </p>
      <ul className="space-y-0.5">
        {roots.map((n) => (
          <TocNode key={n.id} node={n} open={open} activeId={activeId}
            onToggle={onToggle} onGo={onGo} numbered={numbered} />
        ))}
      </ul>
    </nav>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────
// parts     : tableau de chaînes HTML (une par fichier de src/content/…)
// numbered  : numérote les titres (1, 1.1, 1.1.1) dans le texte et le sommaire
// slots     : { nom: <Élément React> } — remplace les <div data-slot="nom"> du contenu
// openFirst : déplie les entrées de premier niveau du sommaire au départ
export default function DocPage({ parts, numbered = true, slots = {}, openFirst = false }) {
  const built = useMemo(() => buildDocument(parts, numbered), [parts, numbered])
  const byId = useMemo(
    () => Object.fromEntries(built.flat.map((n) => [n.id, n])), [built],
  )

  const baseOpen = useMemo(() => (openFirst ? built.roots.map((r) => r.id) : []), [openFirst, built])
  const [open, setOpen]       = useState(() => new Set(baseOpen))   // replié au départ (sauf openFirst)
  const [activeId, setActive] = useState(null)
  const [drawer, setDrawer]   = useState(false)
  const asideRef = useRef(null)
  const locked   = useRef(false)
  const activeRef = useRef(null)

  // Section en cours = dernier titre passé au-dessus du seuil.
  const computeActive = useCallback(() => {
    let current = null
    for (const n of built.flat) {
      const el = document.getElementById(n.id)
      if (!el) continue
      if (el.getBoundingClientRect().top <= ACTIVE_OFFSET) current = n.id
      else break
    }
    if (current === activeRef.current) return
    activeRef.current = current
    setActive(current)
    // la branche de la section en cours s'ouvre (accordéon)
    setOpen(new Set([...baseOpen, ...(current ? ancestorsOf(current, byId) : [])]))
  }, [built, byId, baseOpen])

  useEffect(() => {
    let ticking = false
    const onScroll = () => {
      if (locked.current || ticking) return
      ticking = true
      requestAnimationFrame(() => { ticking = false; computeActive() })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [computeActive])

  // Garde l'entrée active visible dans le sommaire (défilement interne du sommaire seulement).
  useEffect(() => {
    const box = asideRef.current
    const el = box?.querySelector('[aria-current="true"]')
    if (!box || !el) return
    const top = el.offsetTop, bottom = top + el.offsetHeight
    if (top < box.scrollTop) box.scrollTop = Math.max(0, top - 40)
    else if (bottom > box.scrollTop + box.clientHeight) box.scrollTop = bottom - box.clientHeight + 40
  }, [activeId, open])

  const onToggle = useCallback((id) => {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }, [])

  const onGo = useCallback((node) => {
    locked.current = true
    activeRef.current = node.id
    setActive(node.id)
    setOpen(new Set([...baseOpen, ...ancestorsOf(node.id, byId), ...(node.children.length ? [node.id] : [])]))
    setDrawer(false)
    goTo(node.id)
    setTimeout(() => { locked.current = false; computeActive() }, 900)
  }, [byId, computeActive, baseOpen])

  // Renvois « §… » : défilement interne, sans modifier l'adresse de la page.
  const onContentClick = useCallback((e) => {
    const a = e.target.closest?.('a.xref')
    if (!a) return
    e.preventDefault()
    const id = a.getAttribute('data-xref')
    if (byId[id]) onGo(byId[id])
  }, [byId, onGo])

  const tocProps = { roots: built.roots, open, activeId, onToggle, onGo, numbered }

  // Emplacements <div data-slot="…"> du contenu : on y insère les éléments React fournis
  const articleRef = useRef(null)
  const [slotEls, setSlotEls] = useState({})
  useEffect(() => {
    const found = {}
    articleRef.current?.querySelectorAll('[data-slot]').forEach((el) => {
      found[el.getAttribute('data-slot')] = el
    })
    setSlotEls(found)
  }, [built])

  return (
    <div className="lg:flex lg:items-start lg:gap-8">

      {/* Sommaire — petits écrans : bouton + panneau */}
      <div className="lg:hidden sticky top-0 z-20 -mx-6 px-6 py-2 bg-gray-100/95 backdrop-blur border-b border-gray-200 mb-4">
        <button
          type="button"
          onClick={() => setDrawer((d) => !d)}
          aria-expanded={drawer}
          className="text-sm font-medium text-slate-700 bg-white border border-gray-200 rounded px-3 py-1.5 shadow-sm"
        >
          {drawer ? '✕ Fermer le sommaire' : '☰ Sommaire'}
        </button>
        {drawer && (
          <div className="mt-2 max-h-[65vh] overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg p-3">
            <Toc {...tocProps} />
          </div>
        )}
      </div>

      {/* Sommaire — grands écrans : marge de gauche fixe */}
      <aside
        ref={asideRef}
        className="hidden lg:block shrink-0 w-72 sticky top-4 self-start
                   max-h-[calc(100vh-2rem)] overflow-y-auto pr-2"
      >
        <Toc {...tocProps} />
      </aside>

      {/* Contenu */}
      <article
        ref={articleRef}
        className="doc-content flex-1 min-w-0"
        onClick={onContentClick}
        dangerouslySetInnerHTML={{ __html: built.html }}
      />
      {Object.entries(slots).map(([name, node]) =>
        slotEls[name] ? createPortal(node, slotEls[name], name) : null)}
    </div>
  )
}
