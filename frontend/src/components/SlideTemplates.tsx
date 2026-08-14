import { X } from 'lucide-react'

export interface SlideTemplate {
  key: string
  name: string
  hint: string
  slide_type: string
  image_position?: string
  content: string
}

export const SLIDE_TEMPLATES: SlideTemplate[] = [
  {
    key: 'title', name: 'Title Slide', hint: 'Big centred title with a subtitle', slide_type: 'TEXT',
    content: '<h3 style="text-align: center;"><span style="font-size: 1.4em;">Your Title Here</span></h3><p style="text-align: center;"><span style="font-size: 0.85em;">A short subtitle or session objective</span></p>',
  },
  {
    key: 'bullets', name: 'Title + Bullets', hint: 'Heading with key points below', slide_type: 'TEXT',
    content: '<h3>Section Title</h3><ul><li>First key point</li><li>Second key point</li><li>Third key point</li></ul>',
  },
  {
    key: 'steps', name: 'Step by Step', hint: 'Numbered instructions', slide_type: 'TEXT',
    content: '<h3>Step by Step</h3><ol><li>First step</li><li>Second step</li><li>Third step</li></ol>',
  },
  {
    key: 'columns', name: 'Two Columns', hint: 'Side-by-side comparison', slide_type: 'TEXT',
    content: '<h3>Compare &amp; Contrast</h3><div style="display: flex; gap: 24px;"><div style="flex: 1;"><p><b>Column one</b></p><p>Write the first half here…</p></div><div style="flex: 1;"><p><b>Column two</b></p><p>Write the second half here…</p></div></div>',
  },
  {
    key: 'quote', name: 'Quote', hint: 'Centred quote with attribution', slide_type: 'TEXT',
    content: '<p style="text-align: center;"><span style="font-size: 1.4em;"><i>“An inspiring quote goes here.”</i></span></p><p style="text-align: center;"><span style="font-size: 0.85em;">— Attribution</span></p>',
  },
  {
    key: 'image-text', name: 'Image + Text', hint: 'Photo beside your writing', slide_type: 'IMAGE', image_position: 'beside',
    content: '<h3>Picture This</h3><p>Upload an image using the panel on the right, then describe it here.</p>',
  },
]

const PREVIEWS: Record<string, JSX.Element> = {
  title: (
    <div className="flex flex-col items-center justify-center gap-1 h-full">
      <div className="w-14 h-2 bg-slate-400 rounded" />
      <div className="w-10 h-1 bg-slate-300 rounded" />
    </div>
  ),
  bullets: (
    <div className="flex flex-col gap-1 h-full justify-center px-2">
      <div className="w-12 h-1.5 bg-slate-400 rounded" />
      {[0, 1, 2].map(i => (
        <div key={i} className="flex items-center gap-1"><div className="w-1 h-1 bg-slate-300 rounded-full" /><div className="w-10 h-1 bg-slate-300 rounded" /></div>
      ))}
    </div>
  ),
  steps: (
    <div className="flex flex-col gap-1 h-full justify-center px-2">
      <div className="w-12 h-1.5 bg-slate-400 rounded" />
      {['1', '2', '3'].map(n => (
        <div key={n} className="flex items-center gap-1"><span className="text-[6px] text-slate-400 leading-none">{n}.</span><div className="w-10 h-1 bg-slate-300 rounded" /></div>
      ))}
    </div>
  ),
  columns: (
    <div className="flex flex-col gap-1 h-full justify-center px-2">
      <div className="w-12 h-1.5 bg-slate-400 rounded" />
      <div className="flex gap-1.5">
        <div className="flex-1 space-y-0.5"><div className="h-1 bg-slate-300 rounded" /><div className="h-1 bg-slate-200 rounded" /></div>
        <div className="flex-1 space-y-0.5"><div className="h-1 bg-slate-300 rounded" /><div className="h-1 bg-slate-200 rounded" /></div>
      </div>
    </div>
  ),
  quote: (
    <div className="flex flex-col items-center justify-center gap-1 h-full">
      <span className="text-slate-300 text-sm leading-none">“</span>
      <div className="w-12 h-1 bg-slate-300 rounded" />
      <div className="w-8 h-1 bg-slate-200 rounded" />
    </div>
  ),
  'image-text': (
    <div className="flex gap-1.5 h-full items-center px-2">
      <div className="w-8 h-8 bg-slate-300 rounded" />
      <div className="flex-1 space-y-0.5"><div className="h-1 bg-slate-300 rounded" /><div className="h-1 bg-slate-200 rounded" /><div className="h-1 bg-slate-200 rounded w-2/3" /></div>
    </div>
  ),
}

export function SlideTemplatePicker({ onPick, onClose }: { onPick: (t: SlideTemplate) => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose} data-testid="slide-template-modal">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Choose a slide template</h2>
            <p className="text-xs text-slate-400">Drop in a ready-made layout, then fill it with your content</p>
          </div>
          <button onClick={onClose} data-testid="slide-template-close" className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {SLIDE_TEMPLATES.map(t => (
            <button key={t.key} type="button" onClick={() => onPick(t)} data-testid={`slide-template-${t.key}`}
              className="text-left border border-slate-200 rounded-xl p-2.5 hover:border-indigo-300 hover:shadow-sm transition-all group">
              <div className="h-16 bg-slate-50 rounded-lg mb-2 group-hover:bg-indigo-50/60 transition-colors">{PREVIEWS[t.key]}</div>
              <div className="text-xs font-medium text-slate-700">{t.name}</div>
              <div className="text-[10px] text-slate-400 leading-tight mt-0.5">{t.hint}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
