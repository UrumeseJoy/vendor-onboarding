import { BrowserRouter, Link, Route, Routes } from "react-router"

import { HealthProvider } from "@/components/HealthProvider"
import { Layout } from "@/components/Layout"
import { DashboardPage } from "@/pages/DashboardPage"
import { RunPage } from "@/pages/RunPage"
import { SubmitPage } from "@/pages/SubmitPage"
import { VendorPage } from "@/pages/VendorPage"

function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-2 inline-block text-primary hover:underline">Back to the dashboard</Link>
    </div>
  )
}

export default function App() {
  return (
    <HealthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="submit" element={<SubmitPage />} />
            <Route path="runs/:runId" element={<RunPage />} />
            <Route path="vendors/:vendorId" element={<VendorPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </HealthProvider>
  )
}
