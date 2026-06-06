import { Plus, Search, Mail, MoreVertical, Shield, BookOpen, Award } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

const users = [
  { id: "1", name: "Sarah Johnson", email: "sarah@example.com", role: "LEARNER", courses: 4, completed: 3, certificates: 3, joined: "Jan 10, 2024" },
  { id: "2", name: "Mike Peters", email: "mike@example.com", role: "LEARNER", courses: 6, completed: 5, certificates: 5, joined: "Jan 15, 2024" },
  { id: "3", name: "Anna Lee", email: "anna@example.com", role: "INSTRUCTOR", courses: 2, completed: 2, certificates: 2, joined: "Feb 2, 2024" },
  { id: "4", name: "David Chen", email: "david@example.com", role: "LEARNER", courses: 3, completed: 1, certificates: 1, joined: "Feb 20, 2024" },
  { id: "5", name: "Emma Wilson", email: "emma@example.com", role: "ADMIN", courses: 5, completed: 5, certificates: 5, joined: "Mar 1, 2024" },
  { id: "6", name: "James Taylor", email: "james@example.com", role: "LEARNER", courses: 1, completed: 0, certificates: 0, joined: "Apr 5, 2024" },
]

const roleColors: Record<string, string> = {
  ADMIN: "bg-purple-100 text-purple-700",
  INSTRUCTOR: "bg-blue-100 text-blue-700",
  LEARNER: "bg-gray-100 text-gray-600",
}

export default function UsersPage() {
  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Users</h1>
          <p className="text-gray-500 mt-1">{users.length} members total</p>
        </div>
        <Button className="bg-indigo-600 hover:bg-indigo-700 gap-2">
          <Plus className="h-4 w-4" /> Invite User
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        {[
          { label: "Total Users", value: users.length, icon: Shield, color: "text-indigo-600", bg: "bg-indigo-50" },
          { label: "Active Learners", value: users.filter(u => u.role === "LEARNER").length, icon: BookOpen, color: "text-green-600", bg: "bg-green-50" },
          { label: "Certificates Earned", value: users.reduce((a, u) => a + u.certificates, 0), icon: Award, color: "text-yellow-600", bg: "bg-yellow-50" },
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

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Search users..." />
        </div>
        <select className="border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <option>All roles</option>
          <option>Admin</option>
          <option>Instructor</option>
          <option>Learner</option>
        </select>
      </div>

      {/* Table */}
      <Card className="border-0 shadow-sm overflow-hidden">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-6 py-3 font-medium text-gray-500">User</th>
                <th className="text-left px-6 py-3 font-medium text-gray-500">Role</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Courses</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Completed</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Certificates</th>
                <th className="text-right px-6 py-3 font-medium text-gray-500">Joined</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-semibold text-sm flex-shrink-0">
                        {u.name.charAt(0)}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{u.name}</p>
                        <p className="text-xs text-gray-400">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${roleColors[u.role] ?? "bg-gray-100"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right text-gray-600">{u.courses}</td>
                  <td className="px-6 py-4 text-right text-gray-600">{u.completed}</td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-gray-600">{u.certificates}</span>
                  </td>
                  <td className="px-6 py-4 text-right text-gray-400 text-xs">{u.joined}</td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-gray-400 hover:text-gray-700">
                      <MoreVertical className="h-4 w-4" />
                    </button>
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
