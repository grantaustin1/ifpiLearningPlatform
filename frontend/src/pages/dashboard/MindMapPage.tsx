import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactFlow, {
  Background, Controls, MiniMap,
  type Node, type Edge,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from 'lib/api'
import { ArrowLeft, Sparkles, Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

interface MindmapChild { id: string; label: string }
interface MindmapTopic { id: string; label: string; children?: MindmapChild[] }
interface Mindmap { root: { id: string; label: string }; topics: MindmapTopic[] }

/** Radial layout: root centre, topics in a ring around it, children in a
 * sub-ring around each topic. Enough for a first-cut view — users can
 * drag nodes around in react-flow directly. */
function layout(map: Mindmap): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []
  const CX = 500, CY = 300, R1 = 260, R2 = 130

  nodes.push({
    id: map.root.id, position: { x: CX, y: CY },
    data: { label: map.root.label },
    style: { background: '#4f46e5', color: 'white', fontWeight: 700, border: 'none', width: 180, padding: 10, borderRadius: 14 },
    draggable: true,
  })

  const T = map.topics.length || 1
  map.topics.forEach((t, i) => {
    const angle = (i / T) * Math.PI * 2 - Math.PI / 2
    const tx = CX + R1 * Math.cos(angle)
    const ty = CY + R1 * Math.sin(angle)
    nodes.push({
      id: t.id, position: { x: tx, y: ty },
      data: { label: t.label },
      style: { background: '#ec4899', color: 'white', border: 'none', width: 160, padding: 10, borderRadius: 12, fontWeight: 600, fontSize: 13 },
      draggable: true,
    })
    edges.push({ id: `e-${map.root.id}-${t.id}`, source: map.root.id, target: t.id, animated: true, style: { stroke: '#4f46e5', strokeWidth: 2 } })

    const kids = t.children || []
    kids.forEach((c, j) => {
      const kA = angle + ((j - (kids.length - 1) / 2) * 0.35)
      const cx = tx + R2 * Math.cos(kA)
      const cy = ty + R2 * Math.sin(kA)
      nodes.push({
        id: c.id, position: { x: cx, y: cy },
        data: { label: c.label },
        style: { background: 'white', color: '#334155', border: '1px solid #cbd5e1', width: 140, padding: 8, borderRadius: 10, fontSize: 12 },
        draggable: true,
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
  const [loading, setLoading] = useState(false)
  const [maxTopics, setMaxTopics] = useState(6)

  const generate = async () => {
    setLoading(true)
    try {
      const r = await api.post(`/authoring/mindmap/${cid}?max_topics=${maxTopics}`)
      setMap({ root: r.data.root, topics: r.data.topics })
      toast.success(`Generated ${r.data.topics.length} topics`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Mind map failed')
    } finally { setLoading(false) }
  }

  useEffect(() => { generate() /* eslint-disable-next-line */ }, [cid])

  const graph = map ? layout(map) : { nodes: [], edges: [] }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <div className="border-b border-slate-200 bg-white px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={() => nav(`/courses/${cid}/edit`)} className="text-xs text-indigo-600 hover:underline inline-flex items-center gap-1" data-testid="mm-back-btn">
            <ArrowLeft className="h-3 w-3" /> Back to course editor
          </button>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="text-indigo-500 h-5 w-5" /> Course mind map
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-600 inline-flex items-center gap-1">
            Topics:
            <select value={maxTopics} onChange={e => setMaxTopics(Number(e.target.value))}
              className="border border-slate-300 bg-white rounded px-2 py-1 text-xs"
              data-testid="mm-topics-select">
              {[3, 4, 5, 6, 8, 10, 12].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <button onClick={generate} disabled={loading}
            data-testid="mm-regenerate-btn"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-md shadow-indigo-500/20">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {loading ? 'Generating…' : 'Re-generate'}
          </button>
        </div>
      </div>
      <div className="flex-1 relative" style={{ minHeight: 500, height: 'calc(100vh - 80px)' }} data-testid="mm-canvas">
        {loading && !map && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-500 gap-2">
            <Loader2 className="h-6 w-6 animate-spin" /> Analysing course…
          </div>
        )}
        {map && (
          <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView proOptions={{ hideAttribution: true }}>
            <Background gap={20} size={1} color="#e2e8f0" />
            <Controls showInteractive={false} />
            <MiniMap nodeColor={(n) => (n.id.startsWith('t') ? '#ec4899' : n.id === 'root' ? '#4f46e5' : '#cbd5e1')} />
          </ReactFlow>
        )}
      </div>
    </div>
  )
}
