import Link from "next/link"
import { Plus, Search, Filter, BookOpen, Clock, Users, MoreVertical, Edit, Trash2, Eye } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const courses = [
  { id: "1", title: "IFPI Fundamentals", category: "Foundation", slides: 24, enrollments: 89, duration: 45, published: true, coverColor: "bg-blue-500" },
  { id: "2", title: "Music Copyright Law", category: "Legal", slides: 18, enrollments: 67, duration: 60, published: true, coverColor: "bg-purple-500" },
  { id: "3", title: "Compliance Training 2024", category: "Compliance", slides: 32, enrollments: 124, duration: 90, published: true, coverColor: "bg-green-500" },
  { id: "4", title: "Advanced Licensing", category: "Advanced", slides: 15, enrollments: 34, duration: 30, published: false, coverColor: "bg-orange-500" },
  { id: "5", title: "Digital Distribution", category: "Digital", slides: 20, enrollments: 55, duration: 50, published: true, coverColor: "bg-pink-500" },
  { id: "6", title: "Financial Reporting Basics", category: "Finance", slides: 28, enrollments: 41, duration: 75, published: false, coverColor: "bg-indigo-500" },
]

export default function CoursesPage() {
  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Courses</h1>
          <p className="text-gray-500 mt-1">{courses.length} courses total</p>
        </div>
        <Link href="/courses/new">
          <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2">
            <Plus className="h-4 w-4" /> New Course
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="Search courses..."
          />
        </div>
        <Button variant="outline" size="sm" className="gap-2">
          <Filter className="h-4 w-4" /> Filter
        </Button>
        <select className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option>All categories</option>
          <option>Foundation</option>
          <option>Legal</option>
          <option>Compliance</option>
          <option>Advanced</option>
        </select>
      </div>

      {/* Courses Grid */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {courses.map(course => (
          <Card key={course.id} className="border-0 shadow-sm hover:shadow-md transition-shadow overflow-hidden">
            {/* Cover */}
            <div className={`h-32 ${course.coverColor} flex items-center justify-center relative`}>
              <BookOpen className="h-12 w-12 text-white/70" />
              <div className="absolute top-3 right-3">
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                  course.published ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                }`}>
                  {course.published ? "Published" : "Draft"}
                </span>
              </div>
              <div className="absolute top-3 left-3">
                <span className="text-xs font-medium bg-black/30 text-white px-2 py-1 rounded-full">
                  {course.category}
                </span>
              </div>
            </div>
            <CardContent className="p-5">
              <h3 className="font-semibold text-gray-900 mb-3 leading-snug">{course.title}</h3>
              <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
                <span className="flex items-center gap-1"><BookOpen className="h-3 w-3" /> {course.slides} slides</span>
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {course.duration}m</span>
                <span className="flex items-center gap-1"><Users className="h-3 w-3" /> {course.enrollments}</span>
              </div>
              <div className="flex gap-2">
                <Link href={`/courses/${course.id}/edit`} className="flex-1">
                  <Button variant="outline" size="sm" className="w-full gap-1">
                    <Edit className="h-3 w-3" /> Edit
                  </Button>
                </Link>
                <Link href={`/courses/${course.id}`} className="flex-1">
                  <Button size="sm" className="w-full gap-1 bg-indigo-600 hover:bg-indigo-700">
                    <Eye className="h-3 w-3" /> View
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* New course card */}
        <Link href="/courses/new">
          <Card className="border-2 border-dashed border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30 transition-colors h-full flex items-center justify-center cursor-pointer min-h-[240px]">
            <div className="text-center p-6">
              <div className="w-12 h-12 rounded-full bg-indigo-100 flex items-center justify-center mx-auto mb-3">
                <Plus className="h-6 w-6 text-indigo-600" />
              </div>
              <p className="font-medium text-gray-600">Create new course</p>
              <p className="text-sm text-gray-400 mt-1">Build engaging learning content</p>
            </div>
          </Card>
        </Link>
      </div>
    </div>
  )
}
