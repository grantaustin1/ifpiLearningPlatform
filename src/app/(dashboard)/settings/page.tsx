"use client"

import { useState } from "react"
import { GraduationCap, Palette, Globe, Bell, Shield, Save } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

export default function SettingsPage() {
  const [orgName, setOrgName] = useState("IFPI Learning")
  const [primaryColor, setPrimaryColor] = useState("#6366f1")
  const [emailFrom, setEmailFrom] = useState("noreply@ifpi.org")
  const [certExpiry, setCertExpiry] = useState("12")
  const [saved, setSaved] = useState(false)

  const save = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1">Manage your platform configuration</p>
      </div>

      <div className="space-y-6">
        {/* General */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-indigo-600" />
              <CardTitle className="text-base">General</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Platform name</label>
              <input
                value={orgName}
                onChange={e => setOrgName(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Default language</label>
              <select className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                <option>English</option>
                <option>French</option>
                <option>German</option>
                <option>Spanish</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Branding */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <Palette className="h-5 w-5 text-indigo-600" />
              <CardTitle className="text-base">Branding</CardTitle>
            </div>
            <CardDescription>Customize your platform appearance</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Primary color</label>
              <div className="flex items-center gap-3">
                <input type="color" value={primaryColor} onChange={e => setPrimaryColor(e.target.value)} className="w-12 h-10 rounded cursor-pointer border border-gray-300" />
                <input value={primaryColor} onChange={e => setPrimaryColor(e.target.value)} className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Logo</label>
              <div className="border-2 border-dashed border-gray-200 rounded-lg p-6 text-center">
                <p className="text-sm text-gray-400">Drop your logo here or click to upload</p>
                <p className="text-xs text-gray-300 mt-1">PNG, JPG up to 2MB</p>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Font</label>
              <select className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                <option>Inter</option>
                <option>Roboto</option>
                <option>Open Sans</option>
                <option>Montserrat</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Certificates */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-indigo-600" />
              <CardTitle className="text-base">Certificates</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Default validity (months)</label>
              <input
                type="number"
                value={certExpiry}
                onChange={e => setCertExpiry(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Leave blank for no expiry"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Certificate template</label>
              <select className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                <option>Default Template</option>
                <option>Classic</option>
                <option>Modern</option>
                <option>Minimal</option>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-4">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-indigo-600" />
              <CardTitle className="text-base">Notifications</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">From email</label>
              <input
                type="email"
                value={emailFrom}
                onChange={e => setEmailFrom(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            {[
              { label: "Certificate issued", checked: true },
              { label: "Course completion", checked: true },
              { label: "Exam results", checked: true },
              { label: "Weekly digest", checked: false },
            ].map(item => (
              <label key={item.label} className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" defaultChecked={item.checked} className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
                <span className="text-sm text-gray-700">{item.label}</span>
              </label>
            ))}
          </CardContent>
        </Card>

        <Button onClick={save} className="bg-indigo-600 hover:bg-indigo-700 gap-2">
          <Save className="h-4 w-4" />
          {saved ? "Saved!" : "Save changes"}
        </Button>
      </div>
    </div>
  )
}
