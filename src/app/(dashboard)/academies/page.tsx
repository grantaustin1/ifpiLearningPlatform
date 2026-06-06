import { Plus, Globe, Users, Palette } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const academies = [
  { id: "1", name: "IFPI Main Academy", slug: "ifpi-main", members: 248, courses: 12, primaryColor: "#6366f1", isActive: true, created: "Jan 1, 2024" },
  { id: "2", name: "Regional Training Hub", slug: "regional", members: 64, courses: 5, primaryColor: "#16a34a", isActive: true, created: "Mar 15, 2024" },
  { id: "3", name: "Partner Organization Portal", slug: "partners", members: 32, courses: 3, primaryColor: "#d97706", isActive: false, created: "Apr 20, 2024" },
]

export default function AcademiesPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Academies</h1>
          <p className="text-gray-500 mt-1">Branded training portals for each organization</p>
        </div>
        <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2">
          <Plus className="h-4 w-4" /> New Academy
        </Button>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {academies.map(a => (
          <Card key={a.id} className="border-0 shadow-sm hover:shadow-md transition-shadow overflow-hidden">
            <div className="h-2" style={{ backgroundColor: a.primaryColor }} />
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: a.primaryColor }}>
                  {a.name.charAt(0)}
                </div>
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${a.isActive ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  {a.isActive ? "Active" : "Inactive"}
                </span>
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">{a.name}</h3>
              <p className="text-xs text-gray-400 mb-4">/{a.slug}</p>
              <div className="grid grid-cols-2 gap-3 text-center mb-4">
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-lg font-bold text-gray-900">{a.members}</p>
                  <p className="text-xs text-gray-500">Members</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-lg font-bold text-gray-900">{a.courses}</p>
                  <p className="text-xs text-gray-500">Courses</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="flex-1 gap-1.5 text-xs">
                  <Palette className="h-3.5 w-3.5" /> Customize
                </Button>
                <Button variant="outline" size="sm" className="flex-1 gap-1.5 text-xs">
                  <Users className="h-3.5 w-3.5" /> Members
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {/* Add card */}
        <Card className="border-2 border-dashed border-gray-200 hover:border-indigo-300 transition-colors cursor-pointer shadow-none">
          <CardContent className="p-6 flex flex-col items-center justify-center h-full min-h-[240px] text-center">
            <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center mb-3">
              <Plus className="h-6 w-6 text-indigo-600" />
            </div>
            <p className="font-medium text-gray-700 mb-1">Create new academy</p>
            <p className="text-xs text-gray-400">White-label portal for a new organization</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
