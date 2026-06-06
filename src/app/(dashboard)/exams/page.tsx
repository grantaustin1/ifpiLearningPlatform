import Link from "next/link"
import { Plus, Search, ClipboardList, Clock, Users, CheckCircle, Eye, Edit } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const exams = [
  { id: "1", title: "IFPI Foundations Assessment", questions: 25, attempts: 187, passRate: 82, timeLimit: 45, published: true, category: "Foundation" },
  { id: "2", title: "Copyright Law Quiz", questions: 15, attempts: 134, passRate: 76, timeLimit: 20, published: true, category: "Legal" },
  { id: "3", title: "Compliance Certification Exam", questions: 40, attempts: 210, passRate: 71, timeLimit: 60, published: true, category: "Compliance" },
  { id: "4", title: "Financial Reporting Test", questions: 20, attempts: 89, passRate: 88, timeLimit: 30, published: false, category: "Finance" },
  { id: "5", title: "Digital Distribution Knowledge Check", questions: 12, attempts: 67, passRate: 91, timeLimit: 15, published: true, category: "Digital" },
]

export default function ExamsPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Exams</h1>
          <p className="text-gray-500 mt-1">{exams.length} exams total</p>
        </div>
        <Link href="/exams/new">
          <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2">
            <Plus className="h-4 w-4" /> New Exam
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Search exams..." />
        </div>
        <select className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option>All categories</option>
          <option>Foundation</option>
          <option>Legal</option>
          <option>Compliance</option>
          <option>Finance</option>
        </select>
      </div>

      {/* Exams Table */}
      <Card className="border-0 shadow-sm">
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Exam</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Questions</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Attempts</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Pass Rate</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Time Limit</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody>
              {exams.map(exam => (
                <tr key={exam.id} className="border-b last:border-0 hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-gray-900">{exam.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{exam.category}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-sm text-gray-600">
                      <ClipboardList className="h-3.5 w-3.5" />
                      {exam.questions}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-sm text-gray-600">
                      <Users className="h-3.5 w-3.5" />
                      {exam.attempts}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-100 rounded-full">
                        <div
                          className={`h-1.5 rounded-full ${exam.passRate >= 80 ? "bg-green-500" : exam.passRate >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
                          style={{ width: `${exam.passRate}%` }}
                        />
                      </div>
                      <span className={`text-sm font-medium ${exam.passRate >= 80 ? "text-green-600" : exam.passRate >= 60 ? "text-yellow-600" : "text-red-600"}`}>
                        {exam.passRate}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-sm text-gray-600">
                      <Clock className="h-3.5 w-3.5" />
                      {exam.timeLimit}m
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${
                      exam.published ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                    }`}>
                      <CheckCircle className="h-3 w-3" />
                      {exam.published ? "Published" : "Draft"}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 justify-end">
                      <Link href={`/exams/${exam.id}`}>
                        <Button variant="ghost" size="sm" className="gap-1">
                          <Eye className="h-3.5 w-3.5" /> View
                        </Button>
                      </Link>
                      <Button variant="ghost" size="sm" className="gap-1">
                        <Edit className="h-3.5 w-3.5" /> Edit
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
