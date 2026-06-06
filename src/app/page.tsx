import Link from "next/link"
import {
  BookOpen, Award, BarChart3, Users, CheckCircle,
  ArrowRight, GraduationCap, Target, Zap, Route,
  Play, Star, ChevronRight, Building2,
} from "lucide-react"

export default function Home() {
  return (
    <div className="min-h-screen bg-white">

      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/60">
        <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-md shadow-indigo-200">
              <GraduationCap className="text-white" style={{ width: 16, height: 16 }} />
            </div>
            <span className="font-bold text-slate-900 text-[15px]">IFPI Learning</span>
          </Link>

          <div className="hidden md:flex items-center gap-7">
            {["Features", "How it works", "Pricing"].map(item => (
              <Link
                key={item}
                href={`#${item.toLowerCase().replace(/ /g, "-")}`}
                className="text-slate-500 hover:text-slate-900 text-sm font-medium transition-colors"
              >
                {item}
              </Link>
            ))}
          </div>

          <div className="flex items-center gap-2.5">
            <Link href="/login" className="text-sm font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 transition-colors">
              Sign in
            </Link>
            <Link
              href="/register"
              className="text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg shadow-sm hover:shadow-md transition-all"
            >
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-36 pb-28 px-5 hero-mesh relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 right-1/4 w-72 h-72 bg-indigo-100 rounded-full blur-3xl opacity-50" />
          <div className="absolute top-40 right-10 w-48 h-48 bg-violet-100 rounded-full blur-3xl opacity-40" />
        </div>

        <div className="max-w-5xl mx-auto text-center relative">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-indigo-50 border border-indigo-100 text-indigo-700 rounded-full px-4 py-1.5 text-xs font-semibold mb-7 shadow-sm">
            <Zap className="h-3 w-3 fill-indigo-500 text-indigo-500" />
            Trusted by IFPI members worldwide
            <ChevronRight className="h-3 w-3" />
          </div>

          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-slate-900 leading-[1.05] tracking-tight mb-6">
            Training that{" "}
            <span className="relative">
              <span className="bg-gradient-to-r from-indigo-600 via-violet-600 to-indigo-600 bg-clip-text text-transparent">
                scales effortlessly
              </span>
              <span className="absolute -bottom-1 left-0 right-0 h-px bg-gradient-to-r from-indigo-400/0 via-indigo-400/60 to-indigo-400/0" />
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-slate-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Create courses, run exams, issue certificates, and track every learner —
            all from one beautifully designed platform built for IFPI.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              href="/register"
              className="inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-7 py-3.5 rounded-xl shadow-lg shadow-indigo-200 hover:shadow-xl hover:shadow-indigo-200 transition-all hover:-translate-y-0.5 text-[15px]"
            >
              Start for free <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center justify-center gap-2 bg-white border border-slate-200 hover:border-slate-300 text-slate-700 font-semibold px-7 py-3.5 rounded-xl shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5 text-[15px]"
            >
              <Play className="h-4 w-4 fill-slate-600" /> View demo
            </Link>
          </div>

          {/* Trust row */}
          <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-5 text-sm text-slate-400">
            {["No credit card required", "Free 14-day trial", "Cancel anytime"].map(t => (
              <div key={t} className="flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                <span>{t}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats banner */}
      <section className="bg-[#0f172a] py-14">
        <div className="max-w-6xl mx-auto px-5 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { value: "∞",         label: "Courses & Exams",   sub: "No limits" },
            { value: "7",         label: "Question Types",     sub: "Multiple formats" },
            { value: "100%",      label: "Auto-graded",        sub: "Instant results" },
            { value: "Real-time", label: "Reporting",          sub: "Live insights" },
          ].map(s => (
            <div key={s.label}>
              <div className="text-3xl font-extrabold text-white tracking-tight">{s.value}</div>
              <div className="text-[13px] font-semibold text-slate-300 mt-1">{s.label}</div>
              <div className="text-xs text-slate-500 mt-0.5">{s.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-28 px-5">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 mb-3">Everything included</p>
            <h2 className="text-4xl font-extrabold text-slate-900 tracking-tight mb-4">
              All the tools you need to deliver<br className="hidden sm:block" /> great training
            </h2>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto">
              From building your first course to issuing certificates at scale — it's all here.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map(f => (
              <div
                key={f.title}
                className="group bg-white border border-slate-200 hover:border-indigo-200 rounded-2xl p-6 hover:shadow-lg hover:shadow-indigo-50 transition-all duration-200"
              >
                <div className={`w-11 h-11 rounded-xl ${f.iconBg} flex items-center justify-center mb-5`}>
                  <f.icon className={`h-5 w-5 ${f.iconColor}`} />
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-2">{f.title}</h3>
                <p className="text-sm text-slate-500 mb-4 leading-relaxed">{f.description}</p>
                <ul className="space-y-1.5">
                  {f.bullets.map(b => (
                    <li key={b} className="flex items-start gap-2 text-xs text-slate-600">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-28 px-5 bg-slate-50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 mb-3">Simple process</p>
            <h2 className="text-4xl font-extrabold text-slate-900 tracking-tight">Up and running in minutes</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connector line */}
            <div className="hidden md:block absolute top-10 left-1/6 right-1/6 h-px bg-gradient-to-r from-indigo-200 via-indigo-300 to-indigo-200" />
            {steps.map((step, i) => (
              <div key={step.title} className="text-center relative z-10">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white text-xl font-bold flex items-center justify-center mx-auto mb-5 shadow-lg shadow-indigo-200">
                  {i + 1}
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-2">{step.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-28 px-5">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 mb-3">Pricing</p>
            <h2 className="text-4xl font-extrabold text-slate-900 tracking-tight mb-3">
              Simple, predictable pricing
            </h2>
            <p className="text-lg text-slate-500">Flat fee. Unlimited participants. No surprises.</p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {plans.map(plan => (
              <div
                key={plan.name}
                className={`relative rounded-2xl p-7 ${
                  plan.featured
                    ? "bg-[#0f172a] text-white shadow-2xl shadow-slate-900/30 ring-1 ring-indigo-500/30"
                    : "bg-white border border-slate-200 shadow-sm"
                }`}
              >
                {plan.featured && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-indigo-500 to-violet-500 text-white text-[10px] font-bold px-4 py-1 rounded-full tracking-wide uppercase shadow-md">
                    Most Popular
                  </div>
                )}
                <div className="mb-6">
                  <h3 className={`text-base font-bold mb-1 ${plan.featured ? "text-white" : "text-slate-900"}`}>
                    {plan.name}
                  </h3>
                  <div className="flex items-baseline gap-1">
                    <span className={`text-4xl font-extrabold tracking-tight ${plan.featured ? "text-white" : "text-slate-900"}`}>
                      {plan.price}
                    </span>
                    <span className={`text-sm ${plan.featured ? "text-slate-400" : "text-slate-500"}`}>/month</span>
                  </div>
                  <p className={`text-sm mt-2 ${plan.featured ? "text-slate-400" : "text-slate-500"}`}>
                    {plan.description}
                  </p>
                </div>

                <ul className="space-y-2.5 mb-7">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-center gap-2.5 text-sm">
                      <CheckCircle className={`h-4 w-4 flex-shrink-0 ${plan.featured ? "text-indigo-400" : "text-emerald-500"}`} />
                      <span className={plan.featured ? "text-slate-300" : "text-slate-700"}>{f}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/register"
                  className={`flex items-center justify-center gap-2 font-semibold py-3 rounded-xl transition-all text-sm ${
                    plan.featured
                      ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/50"
                      : "bg-slate-900 hover:bg-slate-800 text-white"
                  }`}
                >
                  Get started <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-28 px-5 bg-[#0f172a] relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-3xl mx-auto text-center relative z-10">
          <div className="flex justify-center mb-5">
            {[...Array(5)].map((_, i) => (
              <Star key={i} className="h-5 w-5 text-amber-400 fill-amber-400" />
            ))}
          </div>
          <h2 className="text-4xl font-extrabold text-white tracking-tight mb-4">
            Ready to transform your training?
          </h2>
          <p className="text-lg text-slate-400 mb-8">
            Join IFPI members already using the platform
          </p>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 bg-white text-slate-900 font-bold px-8 py-4 rounded-xl hover:bg-slate-100 transition-all shadow-2xl hover:-translate-y-0.5 text-[15px]"
          >
            Start for free — no credit card required <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#0a0f1e] border-t border-white/5 py-10 px-5">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <GraduationCap style={{ width: 14, height: 14 }} className="text-white" />
            </div>
            <span className="text-white font-semibold text-sm">IFPI Learning Platform</span>
          </div>
          <p className="text-xs text-slate-500">© {new Date().getFullYear()} IFPI Learning. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}

const features = [
  {
    title: "Course Builder",
    description: "Build slide-based courses with rich media in minutes using our intuitive editor.",
    icon: BookOpen,
    iconBg: "bg-blue-50",
    iconColor: "text-blue-600",
    bullets: ["Unlimited courses and slides", "Video, audio, images, PDFs", "Customizable learning paths", "SCORM import support"],
  },
  {
    title: "Exam & Quiz Builder",
    description: "Assess knowledge with fully customizable exams and instant auto-grading.",
    icon: Target,
    iconBg: "bg-violet-50",
    iconColor: "text-violet-600",
    bullets: ["7 question types", "Question bank for reuse", "Auto-grading with feedback", "Time limits & attempt controls"],
  },
  {
    title: "Certificates",
    description: "Automatically issue branded certificates the moment a learner qualifies.",
    icon: Award,
    iconBg: "bg-amber-50",
    iconColor: "text-amber-600",
    bullets: ["Custom certificate templates", "Auto-send on pass", "Unique verification codes", "CPD & compliance ready"],
  },
  {
    title: "Reports & Analytics",
    description: "Real-time insights on learner progress, completion rates, and knowledge gaps.",
    icon: BarChart3,
    iconBg: "bg-emerald-50",
    iconColor: "text-emerald-600",
    bullets: ["Live pass/fail rates", "Per-learner tracking", "Identify knowledge gaps", "On-demand reporting"],
  },
  {
    title: "User Management",
    description: "Manage learners, instructors, and admins with role-based access control.",
    icon: Users,
    iconBg: "bg-pink-50",
    iconColor: "text-pink-600",
    bullets: ["Role-based access control", "Bulk enrolment tools", "Progress reminders", "Self-registration support"],
  },
  {
    title: "Academy Portals",
    description: "Create branded portals for different organisations from a single dashboard.",
    icon: Building2,
    iconBg: "bg-indigo-50",
    iconColor: "text-indigo-600",
    bullets: ["Multiple academies", "Full white-labeling", "Custom URLs & branding", "Reuse content across academies"],
  },
]

const steps = [
  { title: "Create your content",  desc: "Build courses and exams with our intuitive editor. Import existing materials or start from scratch in minutes." },
  { title: "Enrol your learners",  desc: "Invite participants via email or share a link. Set up learning paths and track who's enrolled." },
  { title: "Track & certify",      desc: "Monitor progress in real time, auto-grade exams, and automatically issue certificates on completion." },
]

const plans = [
  {
    name: "Starter",
    price: "R499",
    description: "Perfect to get you started with online training.",
    featured: false,
    features: [
      "Unlimited participants",
      "Up to 500 exam completions/month",
      "Unlimited courses & exams",
      "Auto-generated certificates",
      "Basic reports",
      "1 academy portal",
    ],
  },
  {
    name: "Professional",
    price: "R1,499",
    description: "Everything you need to scale your training.",
    featured: true,
    features: [
      "Unlimited participants",
      "Up to 5,000 exam completions/month",
      "Unlimited courses & exams",
      "Custom certificate templates",
      "Advanced analytics & reports",
      "Multiple academy portals",
      "White-labeling & custom domain",
      "Priority support",
    ],
  },
]
