import { useEffect, useRef, useState } from 'react'
import { Bold, Italic, Underline, List, ListOrdered, RemoveFormatting, Code, Palette, Type, ChevronDown } from 'lucide-react'

const SIZES: [string, string, string][] = [
  ['small', 'Small', '0.85em'],
  ['normal', 'Normal', '1em'],
  ['large', 'Large', '1.4em'],
  ['heading', 'Heading', ''],
]

const COLORS = [
  ['#0f172a', 'Black'], ['#dc2626', 'Red'], ['#ea580c', 'Orange'],
  ['#d97706', 'Amber'], ['#16a34a', 'Green'], ['#2563eb', 'Blue'],
  ['#4f46e5', 'Indigo'], ['#9333ea', 'Purple'], ['#ffffff', 'White'],
]

/** Uncontrolled WYSIWYG: the DOM owns the content after mount; we only read
 *  from it. Re-mount with a fresh `key` to load a different slide. */
export function RichTextEditor({ value, onChange }: { value: string; onChange: (html: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const latest = useRef(value || '')
  const savedRange = useRef<Range | null>(null)
  const [htmlMode, setHtmlMode] = useState(false)
  const [showColors, setShowColors] = useState(false)
  const [showSizes, setShowSizes] = useState(false)

  useEffect(() => {
    if (!htmlMode && ref.current) ref.current.innerHTML = latest.current || ''
  }, [htmlMode])

  const emit = () => {
    if (ref.current) {
      latest.current = ref.current.innerHTML
      onChange(latest.current)
    }
  }

  const exec = (cmd: string, val?: string) => {
    ref.current?.focus()
    document.execCommand(cmd, false, val)
    emit()
  }

  const saveSelection = () => {
    const sel = window.getSelection()
    if (sel && sel.rangeCount > 0 && ref.current?.contains(sel.anchorNode)) {
      savedRange.current = sel.getRangeAt(0).cloneRange()
    }
  }

  const applyColor = (hex: string) => {
    ref.current?.focus()
    const sel = window.getSelection()
    if (savedRange.current && sel) {
      sel.removeAllRanges()
      sel.addRange(savedRange.current)
    }
    document.execCommand('foreColor', false, hex)
    emit()
    setShowColors(false)
  }

  const applySize = (key: string, em: string) => {
    ref.current?.focus()
    const sel = window.getSelection()
    if (savedRange.current && sel) {
      sel.removeAllRanges()
      sel.addRange(savedRange.current)
    }
    document.execCommand('formatBlock', false, key === 'heading' ? 'h3' : 'p')
    // execCommand can't set px/em sizes; use fontSize=7 as a marker then swap to styled spans
    document.execCommand('fontSize', false, '7')
    ref.current?.querySelectorAll('font[size="7"]').forEach(font => {
      const span = document.createElement('span')
      if (key === 'small' || key === 'large') span.style.fontSize = em
      span.innerHTML = font.innerHTML
      font.replaceWith(span)
    })
    emit()
    setShowSizes(false)
  }

  const keepSel = (e: React.MouseEvent) => e.preventDefault()
  const btn = 'inline-flex items-center justify-center h-8 w-8 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors'

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden" data-testid="rich-text-editor">
      <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-slate-100 bg-slate-50 relative flex-wrap">
        <button type="button" onMouseDown={keepSel} onClick={() => exec('bold')} title="Bold" data-testid="rte-bold" className={btn}><Bold className="h-4 w-4" /></button>
        <button type="button" onMouseDown={keepSel} onClick={() => exec('italic')} title="Italic" data-testid="rte-italic" className={btn}><Italic className="h-4 w-4" /></button>
        <button type="button" onMouseDown={keepSel} onClick={() => exec('underline')} title="Underline" data-testid="rte-underline" className={btn}><Underline className="h-4 w-4" /></button>
        <span className="w-px h-5 bg-slate-200 mx-1" />
        <button type="button" onMouseDown={e => { e.preventDefault(); saveSelection() }} onClick={() => { setShowSizes(s => !s); setShowColors(false) }}
          title="Font size" data-testid="rte-size-btn"
          className="inline-flex items-center gap-0.5 h-8 px-2 rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors">
          <Type className="h-4 w-4" /><ChevronDown className="h-3 w-3" />
        </button>
        {showSizes && (
          <div className="absolute top-10 left-16 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 w-32" data-testid="rte-size-menu">
            {SIZES.map(([key, label, em]) => (
              <button key={key} type="button" data-testid={`rte-size-${key}`}
                onMouseDown={e => { e.preventDefault(); applySize(key, em) }}
                className="w-full text-left px-3 py-1.5 text-slate-700 hover:bg-slate-100 transition-colors"
                style={{ fontSize: key === 'heading' ? '1.1em' : em || '1em', fontWeight: key === 'heading' ? 700 : 400 }}>
                {label}
              </button>
            ))}
          </div>
        )}
        <span className="w-px h-5 bg-slate-200 mx-1" />
        <button type="button" onMouseDown={e => { e.preventDefault(); saveSelection() }} onClick={() => { setShowColors(s => !s); setShowSizes(false) }}
          title="Font colour" data-testid="rte-color-btn" className={btn}><Palette className="h-4 w-4" /></button>
        {showColors && (
          <div className="absolute top-10 left-24 z-20 bg-white border border-slate-200 rounded-xl shadow-lg p-2 flex gap-1.5" data-testid="rte-color-palette">
            {COLORS.map(([hex, name]) => (
              <button key={hex} type="button" title={name} data-testid={`rte-color-${name.toLowerCase()}`}
                onMouseDown={e => { e.preventDefault(); applyColor(hex) }}
                className="w-6 h-6 rounded-full border border-slate-200 hover:scale-110 transition-transform"
                style={{ backgroundColor: hex }} />
            ))}
          </div>
        )}
        <span className="w-px h-5 bg-slate-200 mx-1" />
        <button type="button" onMouseDown={keepSel} onClick={() => exec('insertUnorderedList')} title="Bullet list" data-testid="rte-ul" className={btn}><List className="h-4 w-4" /></button>
        <button type="button" onMouseDown={keepSel} onClick={() => exec('insertOrderedList')} title="Numbered list" data-testid="rte-ol" className={btn}><ListOrdered className="h-4 w-4" /></button>
        <span className="w-px h-5 bg-slate-200 mx-1" />
        <button type="button" onMouseDown={keepSel} onClick={() => exec('removeFormat')} title="Clear formatting" data-testid="rte-clear" className={btn}><RemoveFormatting className="h-4 w-4" /></button>
        <button type="button" onClick={() => setHtmlMode(m => !m)} title={htmlMode ? 'Visual editor' : 'Edit raw HTML'} data-testid="rte-html-toggle"
          className={`${btn} ml-auto ${htmlMode ? 'bg-indigo-100 text-indigo-700' : ''}`}><Code className="h-4 w-4" /></button>
      </div>
      {htmlMode ? (
        <textarea defaultValue={latest.current}
          onChange={e => { latest.current = e.target.value; onChange(e.target.value) }}
          rows={12} data-testid="rte-html-textarea"
          className="w-full px-4 py-3 text-xs font-mono focus:outline-none resize-y" />
      ) : (
        <div ref={ref} contentEditable suppressContentEditableWarning
          onInput={emit} onBlur={() => { saveSelection(); emit() }}
          data-testid="rte-visual"
          className="prose prose-sm prose-indigo max-w-none px-4 py-3 min-h-[220px] max-h-[420px] overflow-y-auto focus:outline-none" />
      )}
    </div>
  )
}
