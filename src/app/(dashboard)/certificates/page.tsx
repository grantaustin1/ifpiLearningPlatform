import { Award, Download, Search, CheckCircle, XCircle, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const certificates = [
  { id: "1", user: "Sarah Johnson", type: "Course Completion", item: "IFPI Fundamentals", issued: "Jun 1, 2024", expires: "Jun 1, 2026", score: 88, code: "CERT-001" },
  { id: "2", user: "Mike Peters", type: "Exam Pass", item: "Financial Regulations Exam", issued: "May 28, 2024", expires: null, score: 92, code: "CERT-002" },
  { id: "3", user: "Anna Lee", type: "Course Completion", item: "Compliance Training 2024", issued: "May 20, 2024", expires: "May 20, 2025", score: 95, code: "CERT-003" },
  { id: "4", user: "David Chen", type: "Exam Pass", item: "Music Copyright Law Exam", issued: "May 15, 2024", expires: null, score: 78, code: "CERT-004" },
  { id: "5", user: "Emma Wilson", type: "Learning Path", item: "IFPI Core Curriculum", issued: "May 10, 2024", expires: null, score: 91, code: "CERT-005" },
]

const typeColors: Record<string, string> = {
  "Course Completion": "bg-blue-100 text-blue-700",
  "Exam Pass": "bg-green-100 text-green-700",
  "Learning Path": "bg-purple-100 text-purple-700",
}

export default function CertificatesPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Certificates</h1>
          <p className="text-gray-500 mt-1">{certificates.length} certificates issued</p>
        </div>
        <Button variant="outline" className="gap-2">
          <Download className="h-4 w-4" /> Export
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {[
          { label: "Total Issued", value: "189", icon: Award, color: "text-yellow-600", bg: "bg-yellow-50" },
          { label: "Valid", value: "164", icon: CheckCircle, color: "text-green-600", bg: "bg-green-50" },
          { label: "Expiring Soon", value: "12", icon: Clock, color: "text-orange-600", bg: "bg-orange-50" },
        ].map(s => (
          <Card key={s.label} className="border-0 shadow-sm">
            <CardContent className="p-6 flex items-center gap-4">
              <div className={`p-3 rounded-xl ${s.bg}`}>
                <s.icon className={`h-5 w-5 ${s.color}`} />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{s.value}</p>
                <p className="text-sm text-gray-500">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Search */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Search certificates..." />
        </div>
        <select className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option>All types</option>
          <option>Course Completion</option>
          <option>Exam Pass</option>
          <option>Learning Path</option>
        </select>
      </div>

      {/* Table */}
      <Card className="border-0 shadow-sm overflow-hidden">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-gray-500">Recipient</th>
                <th className="text-left px-6 py-3 font-medium text-gray-500">Type</th>
                <th className="text-left px-6 py-3 font-medium text-gray-500">For</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Score</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Issued</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Expires</th>
                <th className="px-6 py-3 font-medium text-gray-500">Verify Code</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {certificates.map(c => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center text-yellow-700 font-semibold text-sm">
                        {c.user.charAt(0)}
                      </div>
                      <span className="font-medium text-gray-900">{c.user}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${typeColors[c.type]}`}>
                      {c.type}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600">{c.item}</td>
                  <td className="px-6 py-4 text-right font-semibold text-gray-900">{c.score}%</td>
                  <td className="px-6 py-4 text-right text-gray-500 text-xs">{c.issued}</td>
                  <td className="px-6 py-4 text-right">
                    {c.expires ? (
                      <span className="text-xs text-gray-500">{c.expires}</span>
                    ) : (
                      <span className="text-xs text-green-600 font-medium">No expiry</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono">{c.code}</code>
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
