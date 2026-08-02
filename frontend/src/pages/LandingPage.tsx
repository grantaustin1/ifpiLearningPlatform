import { Link } from 'react-router-dom'
<<<<<<< HEAD
import { useQuery } from '@tanstack/react-query'
import { api } from 'lib/api'
import { ArrowRight, BookOpen, CheckCircle, GraduationCap, Sparkles, Star,
         Award, BarChart3, Users, Target, Zap, Clock } from 'lucide-react'

export default function LandingPage() {
  const { data: featured } = useQuery({
    queryKey: ['landing-featured'],
    queryFn: async () => (await api.get('/catalog', { params: { featured: true } })).data,
    staleTime: 5 * 60 * 1000,
  })
  const featuredCourses = (featured?.courses || []).filter((c: any) => c.cover_image).slice(0, 3)

=======
import { ArrowRight, BookOpen, CheckCircle, GraduationCap, Sparkles, Star,
         Award, BarChart3, Users, Target, Zap } from 'lucide-react'

export default function LandingPage() {
>>>>>>> origin/main
  return (
    <div className="min-h-screen bg-white">
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-md shadow-indigo-200">
              <GraduationCap className="text-white h-4 w-4" />
            </div>
            <span className="font-bold text-slate-900 text-[15px]">IFPI Learning</span>
          </Link>
          <div className="flex items-center gap-2.5">
            <Link to="/catalog" data-testid="nav-catalog"
              className="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5">
              Catalog
            </Link>
            <Link to="/login" data-testid="nav-login"
              className="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5">
              Sign in
            </Link>
            <Link to="/register" data-testid="nav-register"
              className="text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg shadow-sm transition-all">
              Get started
            </Link>
          </div>
        </div>
      </nav>

      <section className="pt-36 pb-24 px-5 hero-mesh relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-1/4 w-72 h-72 bg-indigo-100 rounded-full blur-3xl opacity-50" />
          <div className="absolute top-40 right-10 w-48 h-48 bg-violet-100 rounded-full blur-3xl opacity-40" />
        </div>
        <div className="max-w-5xl mx-auto text-center relative">
          <div className="inline-flex items-center gap-2 bg-indigo-50 border border-indigo-100 text-indigo-700 rounded-full px-4 py-1.5 text-xs font-semibold mb-7">
            <Zap className="h-3 w-3 fill-indigo-500 text-indigo-500" />
<<<<<<< HEAD
            Trusted by fitness professionals worldwide
=======
            Trusted by IFPI members worldwide
>>>>>>> origin/main
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-slate-900 leading-[1.05] tracking-tight mb-6 font-display">
            Training that{' '}
            <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-indigo-600 bg-clip-text text-transparent">
<<<<<<< HEAD
              powers the fitness industry
            </span>
          </h1>
          <p className="text-lg sm:text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Accredited courses, auto-graded assessments and verifiable certificates for trainers, coaches, gyms and studios — all from one beautifully designed platform.
=======
              scales effortlessly
            </span>
          </h1>
          <p className="text-lg sm:text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Create courses, run exams, issue certificates, and track every learner — all from one beautifully designed platform.
>>>>>>> origin/main
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/register" data-testid="hero-start-btn"
              className="inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-7 py-3.5 rounded-xl shadow-lg shadow-indigo-200 hover:-translate-y-0.5 transition-all">
              Start for free <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/catalog" data-testid="hero-catalog-btn"
              className="inline-flex items-center justify-center gap-2 bg-white border border-slate-200 hover:border-slate-300 text-slate-700 font-semibold px-7 py-3.5 rounded-xl shadow-sm hover:-translate-y-0.5 transition-all">
              Browse courses
            </Link>
          </div>
          <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-5 text-sm text-slate-400">
            {['No credit card required', 'Free 14-day trial', 'Cancel anytime'].map(t => (
              <div key={t} className="flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-emerald-500" /> {t}
              </div>
            ))}
          </div>
        </div>
      </section>

<<<<<<< HEAD
      {featuredCourses.length > 0 && (
        <section className="py-20 px-5 bg-slate-50/70" data-testid="landing-featured">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-end justify-between mb-10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 mb-3">Start learning today</p>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight font-display">Featured courses</h2>
              </div>
              <Link to="/catalog" className="hidden sm:inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-700">
                Browse all <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="grid md:grid-cols-3 gap-6">
              {featuredCourses.map((c: any) => (
                <Link key={c.id} to={`/catalog/${c.id}`} data-testid={`landing-course-${c.id}`}
                  className="group bg-white rounded-2xl overflow-hidden border border-slate-200 hover:border-indigo-200 hover:shadow-xl hover:shadow-indigo-50 hover:-translate-y-1 transition-all">
                  <div className="h-44 relative overflow-hidden">
                    <img src={c.cover_image} alt={c.title} loading="lazy"
                      className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                    {c.category && <span className="absolute bottom-3 left-4 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/20 backdrop-blur-sm text-white">{c.category}</span>}
                  </div>
                  <div className="p-5">
                    <h3 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">{c.title}</h3>
                    {c.description && <p className="text-sm text-slate-500 mt-1.5 line-clamp-2">{c.description}</p>}
                    <div className="flex items-center gap-4 mt-4 text-xs text-slate-400">
                      <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {c.slide_count} slides</span>
                      {c.duration_minutes && <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {c.duration_minutes}m</span>}
                      <span className="ml-auto font-semibold text-slate-700">{c.price_cents === 0 ? 'Free' : ''}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

=======
>>>>>>> origin/main
      <section className="py-24 px-5">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 mb-3">Everything included</p>
            <h2 className="text-4xl font-extrabold text-slate-900 tracking-tight font-display">All the tools you need</h2>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map(f => (
              <div key={f.title}
                className="bg-white border border-slate-200 hover:border-indigo-200 rounded-2xl p-6 hover:shadow-lg hover:shadow-indigo-50 transition-all">
                <div className={`w-11 h-11 rounded-xl ${f.iconBg} flex items-center justify-center mb-5`}>
                  <f.icon className={`h-5 w-5 ${f.iconColor}`} />
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-2">{f.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-24 px-5 bg-ink-950 relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-3xl mx-auto text-center relative z-10">
          <div className="flex justify-center mb-5">
            {[...Array(5)].map((_, i) => <Star key={i} className="h-5 w-5 text-amber-400 fill-amber-400" />)}
          </div>
          <h2 className="text-4xl font-extrabold text-white tracking-tight mb-4 font-display">Ready to transform your training?</h2>
<<<<<<< HEAD
          <p className="text-lg text-slate-400 mb-8">Join the fitness professionals already learning on the platform</p>
=======
          <p className="text-lg text-slate-400 mb-8">Join IFPI members already using the platform</p>
>>>>>>> origin/main
          <Link to="/register"
            className="inline-flex items-center gap-2 bg-white text-slate-900 font-bold px-8 py-4 rounded-xl hover:bg-slate-100 transition-all shadow-2xl">
            Start for free <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <footer className="bg-[#0a0f1e] py-10 px-5">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <GraduationCap className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-white font-semibold text-sm">IFPI Learning Platform</span>
          </div>
          <p className="text-xs text-slate-500">© {new Date().getFullYear()} IFPI Learning. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

const FEATURES = [
  { title: 'Course Builder', description: 'Build slide-based courses with rich media in minutes using our intuitive editor.',
    icon: BookOpen, iconBg: 'bg-blue-50', iconColor: 'text-blue-600' },
  { title: 'AI-Assisted Authoring', description: 'Generate full courses with quizzes from a single topic prompt.',
    icon: Sparkles, iconBg: 'bg-violet-50', iconColor: 'text-violet-600' },
  { title: 'Auto-Graded Exams', description: 'Multiple question types with instant scoring and certificates.',
    icon: Target, iconBg: 'bg-amber-50', iconColor: 'text-amber-600' },
  { title: 'Real-Time Reports', description: 'Live insights on completion, scores and knowledge gaps.',
    icon: BarChart3, iconBg: 'bg-emerald-50', iconColor: 'text-emerald-600' },
<<<<<<< HEAD
  { title: 'CPD-Ready Certificates', description: 'Branded, auto-issued and publicly verifiable — built for fitness accreditation.',
    icon: Award, iconBg: 'bg-pink-50', iconColor: 'text-pink-600' },
  { title: 'Multi-Academy', description: 'White-label portals for gyms, studios and partner academies from one dashboard.',
=======
  { title: 'Branded Certificates', description: 'Auto-issued with unique verification codes — CPD ready.',
    icon: Award, iconBg: 'bg-pink-50', iconColor: 'text-pink-600' },
  { title: 'Multi-Academy', description: 'White-label portals for partner organisations from one dashboard.',
>>>>>>> origin/main
    icon: Users, iconBg: 'bg-indigo-50', iconColor: 'text-indigo-600' },
]
