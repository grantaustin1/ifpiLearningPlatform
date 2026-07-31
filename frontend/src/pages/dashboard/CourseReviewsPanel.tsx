import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from 'lib/api'
import { Star, EyeOff, Eye, MessageSquareText } from 'lucide-react'
import { toast } from 'sonner'

interface Review {
  id: number
  rating: number
  comment: string
  hidden: boolean
  reviewer_name: string
  created_at: string | null
}

export const CourseReviewsPanel = ({ courseId }: { courseId: number }) => {
  const qc = useQueryClient()
  const { data: reviews = [] } = useQuery<Review[]>({
    queryKey: ['course-reviews', courseId],
    queryFn: async () => (await api.get(`/courses/${courseId}/reviews`)).data,
  })

  const toggleMut = useMutation({
    mutationFn: async (id: number) =>
      (await api.post(`/courses/${courseId}/reviews/${id}/toggle-hidden`)).data,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['course-reviews', courseId] })
      toast.success(d.hidden ? 'Review hidden from the public page' : 'Review is public again')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Could not update review'),
  })

  if (reviews.length === 0) return null

  return (
    <div className="mt-6 pt-4 border-t border-slate-200" data-testid="course-reviews-panel">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 flex items-center gap-1.5 mb-3">
        <MessageSquareText className="h-3.5 w-3.5" /> Learner reviews ({reviews.length})
      </h3>
      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {reviews.map(r => (
          <div key={r.id} data-testid={`admin-review-${r.id}`}
            className={`rounded-lg border p-2.5 text-xs ${r.hidden ? 'border-slate-200 bg-slate-50 opacity-60' : 'border-slate-100 bg-white'}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-0.5 text-amber-400">
                {[1, 2, 3, 4, 5].map(n => (
                  <Star key={n} className={`h-3 w-3 ${r.rating >= n ? 'fill-current' : 'text-slate-200'}`} />
                ))}
              </span>
              <button onClick={() => toggleMut.mutate(r.id)} disabled={toggleMut.isPending}
                data-testid={`toggle-review-${r.id}`}
                title={r.hidden ? 'Show on the public course page' : 'Hide from the public course page'}
                className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-500 hover:text-indigo-600">
                {r.hidden ? <><Eye className="h-3 w-3" /> Unhide</> : <><EyeOff className="h-3 w-3" /> Hide</>}
              </button>
            </div>
            <p className="text-slate-700 mt-1.5 leading-relaxed">{r.comment}</p>
            <p className="text-[10px] text-slate-400 mt-1">
              {r.reviewer_name}{r.created_at ? ` · ${new Date(r.created_at).toLocaleDateString()}` : ''}
              {r.hidden && <span className="ml-1.5 text-red-400 font-semibold">HIDDEN</span>}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
