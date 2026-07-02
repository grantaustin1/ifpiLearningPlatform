import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactFlow, {
  Background, Controls, MiniMap,
  applyNodeChanges,
  type Node, type Edge, type NodeChange,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from 'lib/api'
import { ArrowLeft, Sparkles, Loader2, RefreshCw, Save, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

interface MindmapChild { id: string; label: string }
interface MindmapTopic { id: string; label: string; children?: MindmapChild[] }
interface Mindmap { root: { id: string; label: string }; topics: MindmapTopic[] }
type Positions = Record<string, { x: number; y: number }>

/** Compute radial default positions when the user has no saved layout. */
function defaultPositions(map: Mindmap): Positions {
  const pos: Positions = {}
  const CX = 500, CY = 300, R1 = 260, R2 = 130
  pos[map.root.id] = { x: CX, y: CY }
  const T = map.topics.length || 1
  map.topics.forEach((t, i) => {
    const a = (i / T) * Math.PI * 2 - Math.PI / 2
    pos[t.id] = { x: CX + R1 * Math.cos(a), y: CY + R1 * Math.sin(a) }
    const kids = t.children || []
    kids.forEach((c, j) => {
      const kA = a + ((j - (kids.length - 1) / 2) * 0.35)
      pos[c.id] = { x: pos[t.id].x + R2 * Math.cos(kA), y: pos[t.id].y + R2 * Math.sin(kA) }
    })
  })
  return pos
}

function buildGraph(map: Mindmap, positions: Positions): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    {
      id: map.root.id,
      position: positions[map.root.id] || { x: 500, y: 300 },
      data: { label: map.root.label },
      style: { background: '#4f46e5', color: 'white', fontWeight: 700, border: 'none', width: 180, padding: 10, borderRadius: 14 },
    },
  ]
  const edges: Edge[] = []
  map.topics.forEach(t => {
    nodes.push({
      id: t.id,
      position: positions[t.id] || { x: 700, y: 300 },
      data: { label: t.label },
      style: { background: '#ec4899', color: 'white', border: 'none', width: 160, padding: 10, borderRadius: 12, fontWeight: 600, fontSize: 13 },
    })
    edges.push({ id: `e-${map.root.id}-${t.id}`, source: map.root.id, target: t.id, animated: true, style: { stroke: '#4f46e5', strokeWidth: 2 } })
    ;(t.children || []).forEach(c => {
      nodes.push({
        id: c.id,
        position: positions[c.id] || { x: 850, y: 300 },
        data: { label: c.label },
        style: { background: 'white', color: '#334155', border: '1px solid #cbd5e1', width: 140, padding: 8, borderRadius: 10, fontSize: 12 },
      })
      edges.push({ id: `e-${t.id}-${c.id}`, source: t.id, target: c.id, style: { stroke: '#94a3b8' } })
    })
  })
  return { nodes, edges }
}

export default function MindMapPage() {
  const { courseId } = useParams()
  const nav = useNavigate()
  const cid = Number(courseId)
  const [map, setMap] = useState<Mindmap | null>(null)
  const [positions, setPositions] = useState<Positions>({})
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [maxTopics, setMaxTopics] = useState(6)
  const [hasSaved, setHasSaved] = useState(false)

  const applyGraph = useCallback((m: Mindmap, pos: Positions) => {
    const g = buildGraph(m, pos)
    setNodes(g.nodes); setEdges(g.edges)
  }, [])

  const loadSaved = useCallback(async () => {
    try {
      const r = await api.get(`/authoring/mindmap/${cid}/layout`)
      if (r.data.has_saved) {
        setMap(r.data.graph); setPositions(r.data.positions)
        applyGraph(r.data.graph, r.data.positions)
        setHasSaved(true); setDirty(false)
        return true
      }
    } catch { /* fall through */ }
    return false
  }, [cid, applyGraph])

  const generate = useCallback(async (force: boolean = false) => {
    setLoading(true)
    try {
      if (!force) {
        const restored = await loadSaved()
        if (restored) { toast.success('Loaded saved layout'); return }
      }
      const r = await api.post(`/authoring/mindmap/${cid}?max_topics=${maxTopics}`)
      const m: Mindmap = { root: r.data.root, topics: r.data.topics }
      const pos = defaultPositions(m)
      setMap(m); setPositions(pos); applyGraph(m, pos)
      setDirty(true); setHasSaved(false)
      toast.success(`Generated ${r.data.topics.length} topics`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Mind map failed')
    } finally { setLoading(false) }
  }, [cid, maxTopics, applyGraph, loadSaved])

  useEffect(() => { generate(false) }, [cid]) // eslint-disable-line react-hooks/exhaustive-deps

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes(ns => {
      const next = applyNodeChanges(changes, ns)
      // Any position change → mark dirty, snapshot positions
      if (changes.some(c => c.type === 'position')) {
        setDirty(true)
        setPositions(p => {
          const np = { ...p }
          next.forEach(n => { np[n.id] = { x: n.position.x, y: n.position.y } })
          return np
        })
      }
      return next
    })
  }, [])

  const save = async () => {
    if (!map) return
    setSaving(true)
    try {
      // Snapshot the current React-Flow viewport as a base64 SVG so the
      // course card can render a preview without re-running the LLM.
      let thumbnail_svg: string | null = null
      try {
        const svgEl = document.querySelector('.react-flow__viewport')?.closest('svg') as SVGElement | null
        if (svgEl) {
          const clone = svgEl.cloneNode(true) as SVGElement
          clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
          clone.setAttribute('width', '400')
          clone.setAttribute('height', '260')
          const raw = new XMLSerializer().serializeToString(clone)
          if (raw.length < 180_000) {
            thumbnail_svg = btoa(unescape(encodeURIComponent(raw)))
          }
        }
      } catch { /* thumbnail is best-effort */ }

      await api.put(`/authoring/mindmap/${cid}/layout`, {
        graph: map, positions, thumbnail_svg,
      })
      toast.success('Layout saved')
      setDirty(false); setHasSaved(true)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Save failed')
    } finally { setSaving(false) }
  }

  const clearSaved = async () => {
    if (!window.confirm('Clear the saved layout? The next visit will regenerate from scratch.')) return
    await api.delete(`/authoring/mindmap/${cid}/layout`)
    setHasSaved(false)
    toast.success('Saved layout cleared')
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-8 py-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <button onClick={() => nav(`/courses/${cid}/edit`)} className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1" data-testid="mm-back-btn">
            <ArrowLeft className="h-3 w-3" /> Back to course editor
          </button>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="text-indigo-500 h-5 w-5" /> Course mind map
          </h1>
          {dirty && <span className="text-[11px] font-semibold text-orange-600 uppercase tracking-wide" data-testid="mm-dirty-flag">Unsaved changes</span>}
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-600 inline-flex items-center gap-1">
            Topics:
            <select value={maxTopics} onChange={e => setMaxTopics(Number(e.target.value))}
              className="border border-slate-300 bg-white rounded px-2 py-1 text-xs"
              data-testid="mm-topics-select">
              {[3, 4, 5, 6, 8, 10, 12].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <button onClick={() => generate(true)} disabled={loading}
            data-testid="mm-regenerate-btn"
            className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-900 disabled:bg-slate-300 text-white px-3 py-2 rounded-lg text-xs font-semibold">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Re-generate
          </button>
          <button onClick={save} disabled={saving || !dirty || !map}
            data-testid="mm-save-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-md shadow-indigo-500/20">
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save layout
          </button>
          {hasSaved && (
            <button onClick={clearSaved} className="text-xs text-rose-600 hover:underline inline-flex items-center gap-1" data-testid="mm-clear-saved-btn">
              <Trash2 className="h-3 w-3" /> Clear saved
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 relative" style={{ minHeight: 500, height: 'calc(100vh - 80px)' }} data-testid="mm-canvas">
        {loading && !map && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-500 gap-2">
            <Loader2 className="h-6 w-6 animate-spin" /> Analysing course…
          </div>
        )}
        {map && (
          <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange}
            fitView proOptions={{ hideAttribution: true }}>
            <Background gap={20} size={1} color="#e2e8f0" />
            <Controls showInteractive={false} />
            <MiniMap nodeColor={(n) => (n.id.startsWith('t') ? '#ec4899' : n.id === 'root' ? '#4f46e5' : '#cbd5e1')} />
          </ReactFlow>
        )}
      </div>
    </div>
  )
}
