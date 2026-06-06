"use client"

import { useState, useEffect, useRef } from "react"
import {
  MessageCircle, Pin, Trash2, Reply, Edit3, Check, X,
  Loader2, ChevronDown, ChevronUp,
} from "lucide-react"

interface CommentUser { id: string; name: string | null; role: string }
interface Comment {
  id: string
  content: string | null
  isPinned: boolean
  isDeleted: boolean
  createdAt: string
  updatedAt: string
  user: CommentUser | null
  isOwn: boolean
  isModerator: boolean
  replies: Comment[]
}

const ROLE_COLORS: Record<string, string> = {
  ADMIN:      "bg-purple-100 text-purple-700",
  SUPER_ADMIN:"bg-purple-100 text-purple-700",
  INSTRUCTOR: "bg-blue-100 text-blue-700",
  LEARNER:    "bg-slate-100 text-slate-500",
}

function timeAgo(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return "just now"
  const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24); if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })
}

function Avatar({ name, role }: { name: string | null; role: string }) {
  const initials = (name ?? "?").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
  const isAdmin = role === "ADMIN" || role === "SUPER_ADMIN"
  const isInstructor = role === "INSTRUCTOR"
  const bg = isAdmin ? "from-purple-500 to-violet-600" : isInstructor ? "from-blue-500 to-indigo-600" : "from-indigo-400 to-indigo-500"
  return (
    <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${bg} flex items-center justify-center text-white text-xs font-bold flex-shrink-0`}>
      {initials}
    </div>
  )
}

function ComposeBox({
  placeholder = "Share your thoughts...",
  onSubmit,
  onCancel,
  initialValue = "",
  autoFocus = false,
}: {
  placeholder?: string
  onSubmit: (content: string) => Promise<void>
  onCancel?: () => void
  initialValue?: string
  autoFocus?: boolean
}) {
  const [value, setValue] = useState(initialValue)
  const [submitting, setSubmitting] = useState(false)
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (autoFocus) ref.current?.focus()
  }, [autoFocus])

  const handleSubmit = async () => {
    if (!value.trim() || submitting) return
    setSubmitting(true)
    try { await onSubmit(value.trim()) } finally { setSubmitting(false) }
    setValue("")
  }

  return (
    <div className="space-y-2">
      <textarea
        ref={ref}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit() }}
        placeholder={placeholder}
        rows={3}
        className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
      />
      <div className="flex items-center justify-end gap-2">
        {onCancel && (
          <button onClick={onCancel} className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-700 rounded-lg hover:bg-slate-50 transition-colors">
            Cancel
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={!value.trim() || submitting}
          className="flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><Check className="h-3.5 w-3.5" /> Post</>}
        </button>
      </div>
    </div>
  )
}

function CommentCard({
  comment,
  courseId,
  depth = 0,
  onUpdate,
}: {
  comment: Comment
  courseId: string
  depth?: number
  onUpdate: (id: string, patch: Partial<Comment> | null) => void
}) {
  const [replying, setReplying] = useState(false)
  const [editing, setEditing] = useState(false)
  const [showReplies, setShowReplies] = useState(true)

  const handleEdit = async (content: string) => {
    const res = await fetch(`/api/comments/${comment.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    })
    if (res.ok) {
      const data = await res.json()
      onUpdate(comment.id, { content: data.content, updatedAt: data.updatedAt })
      setEditing(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm("Delete this comment?")) return
    const res = await fetch(`/api/comments/${comment.id}`, { method: "DELETE" })
    if (res.ok) onUpdate(comment.id, null) // null = soft delete
  }

  const handlePin = async () => {
    const res = await fetch(`/api/comments/${comment.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isPinned: !comment.isPinned }),
    })
    if (res.ok) {
      const data = await res.json()
      onUpdate(comment.id, { isPinned: data.isPinned })
    }
  }

  const handleReply = async (content: string) => {
    const res = await fetch(`/api/courses/${courseId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, parentId: comment.id }),
    })
    if (res.ok) {
      const newReply = await res.json()
      onUpdate(comment.id, {
        replies: [...comment.replies, newReply],
      })
      setReplying(false)
    }
  }

  if (comment.isDeleted && comment.replies.length === 0) return null

  return (
    <div className={depth > 0 ? "ml-10 mt-2" : ""}>
      <div className={`rounded-xl p-4 transition-colors ${comment.isPinned ? "bg-amber-50 border border-amber-100" : "bg-white border border-slate-100"}`}>
        {comment.isPinned && (
          <div className="flex items-center gap-1 mb-2">
            <Pin className="h-3 w-3 text-amber-500" />
            <span className="text-xs font-medium text-amber-600">Pinned</span>
          </div>
        )}

        {comment.isDeleted ? (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-slate-100 flex-shrink-0" />
            <p className="text-sm text-slate-400 italic">[Comment removed]</p>
          </div>
        ) : (
          <>
            <div className="flex items-start gap-2.5">
              <Avatar name={comment.user?.name ?? null} role={comment.user?.role ?? "LEARNER"} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-800">{comment.user?.name ?? "Unknown"}</span>
                  {comment.user?.role && comment.user.role !== "LEARNER" && (
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLORS[comment.user.role] ?? "bg-slate-100"}`}>
                      {comment.user.role}
                    </span>
                  )}
                  <span className="text-xs text-slate-400">{timeAgo(comment.createdAt)}</span>
                  {comment.updatedAt !== comment.createdAt && (
                    <span className="text-[10px] text-slate-300">(edited)</span>
                  )}
                </div>

                {editing ? (
                  <div className="mt-2">
                    <ComposeBox
                      initialValue={comment.content ?? ""}
                      onSubmit={handleEdit}
                      onCancel={() => setEditing(false)}
                      autoFocus
                    />
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{comment.content}</p>
                )}

                {!editing && (
                  <div className="flex items-center gap-3 mt-2">
                    {depth === 0 && (
                      <button
                        onClick={() => setReplying(!replying)}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-600 transition-colors"
                      >
                        <Reply className="h-3.5 w-3.5" /> Reply
                      </button>
                    )}
                    {comment.isOwn && (
                      <button
                        onClick={() => setEditing(true)}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-600 transition-colors"
                      >
                        <Edit3 className="h-3.5 w-3.5" /> Edit
                      </button>
                    )}
                    {(comment.isOwn || comment.isModerator) && (
                      <button
                        onClick={handleDelete}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Delete
                      </button>
                    )}
                    {comment.isModerator && depth === 0 && (
                      <button
                        onClick={handlePin}
                        className={`flex items-center gap-1 text-xs transition-colors ${comment.isPinned ? "text-amber-500 hover:text-amber-600" : "text-slate-400 hover:text-amber-500"}`}
                      >
                        <Pin className="h-3.5 w-3.5" /> {comment.isPinned ? "Unpin" : "Pin"}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Replies */}
      {depth === 0 && comment.replies.length > 0 && (
        <div className="ml-10 mt-1">
          <button
            onClick={() => setShowReplies(!showReplies)}
            className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 mb-2 transition-colors"
          >
            {showReplies ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {comment.replies.length} {comment.replies.length === 1 ? "reply" : "replies"}
          </button>
          {showReplies && (
            <div className="space-y-2">
              {comment.replies.map(r => (
                <div key={r.id} className="rounded-xl p-3 bg-white border border-slate-100">
                  <div className="flex items-start gap-2.5">
                    <Avatar name={r.user?.name ?? null} role={r.user?.role ?? "LEARNER"} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-800">{r.user?.name ?? "Unknown"}</span>
                        {r.user?.role && r.user.role !== "LEARNER" && (
                          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLORS[r.user.role] ?? "bg-slate-100"}`}>
                            {r.user.role}
                          </span>
                        )}
                        <span className="text-xs text-slate-400">{timeAgo(r.createdAt)}</span>
                      </div>
                      <p className="mt-1 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{r.content}</p>
                      {(r.isOwn || r.isModerator) && (
                        <div className="flex items-center gap-3 mt-2">
                          {r.isOwn && (
                            <button
                              onClick={async () => {
                                const newContent = prompt("Edit reply:", r.content ?? "")
                                if (!newContent || !newContent.trim()) return
                                const res = await fetch(`/api/comments/${r.id}`, {
                                  method: "PATCH",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({ content: newContent.trim() }),
                                })
                                if (res.ok) {
                                  const data = await res.json()
                                  onUpdate(comment.id, {
                                    replies: comment.replies.map(x =>
                                      x.id === r.id ? { ...x, content: data.content } : x
                                    ),
                                  })
                                }
                              }}
                              className="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-600 transition-colors"
                            >
                              <Edit3 className="h-3.5 w-3.5" /> Edit
                            </button>
                          )}
                          <button
                            onClick={async () => {
                              if (!confirm("Delete this reply?")) return
                              const res = await fetch(`/api/comments/${r.id}`, { method: "DELETE" })
                              if (res.ok) {
                                onUpdate(comment.id, {
                                  replies: comment.replies.filter(x => x.id !== r.id),
                                })
                              }
                            }}
                            className="flex items-center gap-1 text-xs text-slate-400 hover:text-red-500 transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reply compose box */}
      {replying && depth === 0 && (
        <div className="ml-10 mt-2">
          <ComposeBox
            placeholder={`Reply to ${comment.user?.name ?? "this comment"}...`}
            onSubmit={handleReply}
            onCancel={() => setReplying(false)}
            autoFocus
          />
        </div>
      )}
    </div>
  )
}

export function Discussion({ courseId }: { courseId: string }) {
  const [comments, setComments] = useState<Comment[]>([])
  const [total, setTotal] = useState(0)
  const [isModerator, setIsModerator] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const res = await fetch(`/api/courses/${courseId}/comments`)
      if (res.ok) {
        const data = await res.json()
        setComments(data.comments ?? [])
        setTotal(data.total ?? 0)
        setIsModerator(data.isModerator ?? false)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [courseId])

  const handlePost = async (content: string) => {
    const res = await fetch(`/api/courses/${courseId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    })
    if (res.ok) {
      const newComment = await res.json()
      newComment.isModerator = isModerator
      setComments(prev => [newComment, ...prev])
      setTotal(t => t + 1)
    }
  }

  const handleUpdate = (id: string, patch: Partial<Comment> | null) => {
    setComments(prev => prev.map(c => {
      if (c.id === id) {
        if (patch === null) return { ...c, isDeleted: true } // soft delete
        return { ...c, ...patch }
      }
      return c
    }).filter(c => !(c.isDeleted && c.replies.length === 0)))
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <MessageCircle className="h-5 w-5 text-indigo-500" />
        <h2 className="text-base font-semibold text-slate-800">
          Discussion
          {total > 0 && <span className="ml-2 text-xs font-normal text-slate-400">{total} {total === 1 ? "comment" : "comments"}</span>}
        </h2>
      </div>

      {/* Compose */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <ComposeBox placeholder="Ask a question or share a thought..." onSubmit={handlePost} />
      </div>

      {/* Comments */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 text-indigo-400 animate-spin" />
        </div>
      ) : comments.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <MessageCircle className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No comments yet. Be the first!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {comments.map(c => (
            <CommentCard
              key={c.id}
              comment={{ ...c, isModerator }}
              courseId={courseId}
              depth={0}
              onUpdate={handleUpdate}
            />
          ))}
        </div>
      )}
    </div>
  )
}
