import { Plus, BookOpen, ClipboardList, ArrowRight, GripVertical, CheckCircle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const paths = [
  {
    id: "1",
    title: "IFPI Core Curriculum",
    description: "Complete foundation training for new IFPI members",
    isPublished: true,
    items: [
      { type: "course", name: "IFPI Fundamentals", required: true },
      { type: "exam", name: "Fundamentals Assessment", required: true },
      { type: "course", name: "Music Copyright Law", required: true },
      { type: "course", name: "Compliance Training 2024", required: false },
    ],
    enrolled: 89,
  },
  {
    id: "2",
    title: "Advanced Certification Track",
    description: "For experienced members pursuing advanced credentials",
    isPublished: false,
    items: [
      { type: "course", name: "Advanced Licensing", required: true },
      { type: "course", name: "Financial Reporting Basics", required: true },
      { type: "exam", name: "Advanced Certification Exam", required: true },
    ],
    enrolled: 34,
  },
]

export default function LearningPathsPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Learning Paths</h1>
          <p className="text-gray-500 mt-1">Structured training journeys for your learners</p>
        </div>
        <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2">
          <Plus className="h-4 w-4" /> New Path
        </Button>
      </div>

      <div className="grid gap-6">
        {paths.map(path => (
          <Card key={path.id} className="border-0 shadow-sm hover:shadow-md transition-shadow">
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900 text-lg">{path.title}</h3>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${path.isPublished ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {path.isPublished ? "Published" : "Draft"}
                    </span>
                  </div>
                  <p className="text-gray-500 text-sm">{path.description}</p>
                </div>
                <div className="text-right ml-4">
                  <p className="text-2xl font-bold text-gray-900">{path.enrolled}</p>
                  <p className="text-xs text-gray-400">enrolled</p>
                </div>
              </div>

              {/* Path items */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                {path.items.map((item, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border ${
                      item.type === "course" ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-purple-50 border-purple-200 text-purple-700"
                    }`}>
                      {item.type === "course" ? <BookOpen className="h-3.5 w-3.5" /> : <ClipboardList className="h-3.5 w-3.5" />}
                      {item.name}
                      {item.required && <span className="text-xs opacity-70">*</span>}
                    </div>
                    {i < path.items.length - 1 && <ArrowRight className="h-4 w-4 text-gray-300 flex-shrink-0" />}
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between">
                <p className="text-xs text-gray-400">
                  {path.items.length} items · {path.items.filter(i => i.required).length} required
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">Edit</Button>
                  <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700">View</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Empty state add */}
        <Card className="border-2 border-dashed border-gray-200 hover:border-indigo-300 transition-colors cursor-pointer shadow-none">
          <CardContent className="p-8 flex flex-col items-center text-center">
            <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center mb-3">
              <Plus className="h-6 w-6 text-indigo-600" />
            </div>
            <p className="font-medium text-gray-700 mb-1">Create a learning path</p>
            <p className="text-sm text-gray-400">Chain courses and exams into a structured journey</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
