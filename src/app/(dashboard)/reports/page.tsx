import { BarChart3, TrendingUp, Users, BookOpen, Award, ClipboardList, Download } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const topCourses = [
  { name: "IFPI Fundamentals", enrolled: 89, completed: 71, rate: 80 },
  { name: "Compliance Training 2024", enrolled: 124, completed: 98, rate: 79 },
  { name: "Music Copyright Law", enrolled: 67, completed: 51, rate: 76 },
  { name: "Digital Distribution", enrolled: 55, completed: 38, rate: 69 },
  { name: "Financial Reporting Basics", enrolled: 41, completed: 22, rate: 54 },
]

const examStats = [
  { name: "IFPI Fundamentals Exam", attempts: 89, passed: 74, avgScore: 82, passRate: 83 },
  { name: "Copyright Law Assessment", attempts: 67, passed: 52, avgScore: 76, passRate: 78 },
  { name: "Compliance Quiz", attempts: 124, passed: 109, avgScore: 88, passRate: 88 },
]

const monthlyData = [
  { month: "Jan", enrollments: 42, completions: 28 },
  { month: "Feb", enrollments: 58, completions: 35 },
  { month: "Mar", enrollments: 65, completions: 48 },
  { month: "Apr", enrollments: 71, completions: 55 },
  { month: "May", enrollments: 88, completions: 67 },
  { month: "Jun", enrollments: 95, completions: 74 },
]

const maxVal = Math.max(...monthlyData.map(d => d.enrollments))

export default function ReportsPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reports & Analytics</h1>
          <p className="text-gray-500 mt-1">Track training performance and learner progress</p>
        </div>
        <Button variant="outline" className="gap-2">
          <Download className="h-4 w-4" /> Export CSV
        </Button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {[
          { label: "Total Learners", value: "248", sub: "+18 this week", icon: Users, color: "text-blue-600", bg: "bg-blue-50" },
          { label: "Courses Completed", value: "1,024", sub: "across all courses", icon: BookOpen, color: "text-green-600", bg: "bg-green-50" },
          { label: "Avg. Pass Rate", value: "78%", sub: "+5% from last month", icon: TrendingUp, color: "text-indigo-600", bg: "bg-indigo-50" },
          { label: "Certificates Issued", value: "189", sub: "+12 this month", icon: Award, color: "text-yellow-600", bg: "bg-yellow-50" },
        ].map(stat => (
          <Card key={stat.label} className="border-0 shadow-sm">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-500">{stat.label}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{stat.value}</p>
                  <p className="text-xs text-gray-400 mt-1">{stat.sub}</p>
                </div>
                <div className={`p-3 rounded-xl ${stat.bg}`}>
                  <stat.icon className={`h-5 w-5 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-6 mb-8">
        {/* Monthly Chart */}
        <Card className="lg:col-span-3 border-0 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Enrollments vs. Completions</CardTitle>
            <CardDescription>Last 6 months</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-3 h-48">
              {monthlyData.map(d => (
                <div key={d.month} className="flex-1 flex flex-col items-center gap-1">
                  <div className="flex items-end gap-0.5 w-full">
                    <div
                      className="flex-1 bg-indigo-500 rounded-t-sm"
                      style={{ height: `${(d.enrollments / maxVal) * 160}px` }}
                      title={`Enrollments: ${d.enrollments}`}
                    />
                    <div
                      className="flex-1 bg-green-400 rounded-t-sm"
                      style={{ height: `${(d.completions / maxVal) * 160}px` }}
                      title={`Completions: ${d.completions}`}
                    />
                  </div>
                  <span className="text-xs text-gray-400">{d.month}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-4 mt-3">
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-indigo-500 rounded-sm" /><span className="text-xs text-gray-500">Enrollments</span></div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-green-400 rounded-sm" /><span className="text-xs text-gray-500">Completions</span></div>
            </div>
          </CardContent>
        </Card>

        {/* Completion Rates */}
        <Card className="lg:col-span-2 border-0 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base">Completion Rates</CardTitle>
            <CardDescription>By course</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {topCourses.map(c => (
              <div key={c.name}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-700 truncate max-w-[70%]">{c.name}</span>
                  <span className="text-xs font-semibold text-gray-900">{c.rate}%</span>
                </div>
                <div className="h-1.5 bg-gray-100 rounded-full">
                  <div
                    className="h-1.5 bg-indigo-600 rounded-full"
                    style={{ width: `${c.rate}%` }}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Exam Stats Table */}
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Exam Performance</CardTitle>
              <CardDescription>Pass rates and average scores</CardDescription>
            </div>
            <ClipboardList className="h-5 w-5 text-gray-400" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 font-medium text-gray-500">Exam</th>
                  <th className="text-right py-2 font-medium text-gray-500">Attempts</th>
                  <th className="text-right py-2 font-medium text-gray-500">Passed</th>
                  <th className="text-right py-2 font-medium text-gray-500">Avg. Score</th>
                  <th className="text-right py-2 font-medium text-gray-500">Pass Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {examStats.map(e => (
                  <tr key={e.name} className="hover:bg-gray-50">
                    <td className="py-3 font-medium text-gray-900">{e.name}</td>
                    <td className="py-3 text-right text-gray-600">{e.attempts}</td>
                    <td className="py-3 text-right text-gray-600">{e.passed}</td>
                    <td className="py-3 text-right text-gray-600">{e.avgScore}%</td>
                    <td className="py-3 text-right">
                      <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                        e.passRate >= 80 ? "bg-green-100 text-green-700" :
                        e.passRate >= 60 ? "bg-yellow-100 text-yellow-700" : "bg-red-100 text-red-700"
                      }`}>{e.passRate}%</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
