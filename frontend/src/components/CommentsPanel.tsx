import { useEffect, useState } from 'react'
import { api } from 'lib/api'
import { useAuth } from 'contexts/AuthContext'
import { MessageCircle, Send, Trash2 } from 'lucide-react'
import { timeAgo } from 'lib/utils'
import { toast } from 'sonner'
import type { Comment } from 'types'

export default function CommentsPanel({ slideId }: { slideId: number }) {
  const { user, hasRole } = useAuth()
  const [comments, setComments] = useState<Comment[]>([])
  const [body, setBody] = useState('')
  const [posting, setPosting] = useState(false)
  const isMod = hasRole('ADMIN', 'SUPER_ADMIN', 'INSTRUCTOR')

  useEffect(() => {
    const ctrl = new AbortController()
    api.get<Comment[]>(`/slides/${slideId}/comments`, { signal: ctrl.signal })
      .then(r => setComments(r.data))
      .catch(() => {})
    return () => ctrl.abort()
  }, [slideId])

  const refresh = () =>
    api.get<Comment[]>(`/slides/${slideId}/comments`)
      .then(r => setComments(r.data))
      .catch(() => {})

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!body.trim()) return
    setPosting(true)
    try {
      const r = await api.post<Comment>(`/slides/${slideId}/comments`, { body })
      setComments(prev => [...prev, r.data])
      setBody('')
    } catch {
      toast.error('Could not post comment')
    } finally {
      setPosting(false)
    }
  }

  const del = async (id: number) => {
    await api.delete(`/slides/${slideId}/comments/${id}`)
    refresh()
  }

  return (
    <div className="mt-10 border-t border-slate-200 pt-6" data-testid="comments-panel">
      <h3 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
        <MessageCircle className="h-4 w-4 text-indigo-500" /> Discussion ({comments.length})
      </h3>
      <div className="space-y-3 mb-4">
        {comments.length === 0 ? (
          <p className="text-xs text-slate-400">No comments yet — start the discussion.</p>
        ) : (
          comments.map(c => (
            <div key={c.id} className="bg-slate-50 rounded-xl p-3" data-testid={`comment-${c.id}`}>
              <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                <span className="font-semibold text-slate-700">{c.user_name || 'Anonymous'}</span>
                <span>·</span>
                <span>{timeAgo(c.created_at)}</span>
                {(c.user_id === user?.id || isMod) && (
                  <button
                    onClick={() => del(c.id)}
                    data-testid={`comment-delete-${c.id}`}
                    className="ml-auto text-slate-300 hover:text-red-500"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{c.body}</p>
            </div>
          ))
        )}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={body}
          onChange={e => setBody(e.target.value)}
          placeholder="Add a comment…"
          data-testid="comment-input"
          className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
        />
        <button
          type="submit"
          disabled={posting || !body.trim()}
          data-testid="comment-submit"
          className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-2 rounded-lg"
        >
          <Send className="h-3.5 w-3.5" /> Post
        </button>
      </form>
    </div>
  )
}
