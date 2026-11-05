import { CircleCheckBig, Cpu, FilePlus2, LayoutDashboard, WifiOff } from "lucide-react"
import { NavLink, Outlet } from "react-router"

import { ThemeToggle } from "@/components/ThemeToggle"
import { useHealth } from "@/hooks/useHealth"
import { API_URL } from "@/lib/api"
import { cn } from "@/lib/utils"

function NavItem({ to, icon: Icon, label }: { to: string; icon: typeof LayoutDashboard; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cn(
          "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
          isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
        )
      }
    >
      <Icon className="size-4" aria-hidden />
      <span className="hidden sm:inline">{label}</span>
    </NavLink>
  )
}

function ModeBadge() {
  const { health } = useHealth()
  if (!health) return null
  const gemini = health.extractor_mode === "gemini"
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs text-muted-foreground"
      title={gemini ? "Documents are read by Gemini" : "Documents are read by the offline mock extractor"}
    >
      <Cpu className="size-3.5" aria-hidden />
      {gemini ? "Gemini" : "Mock"}
    </span>
  )
}

function OfflineBanner() {
  const { offline } = useHealth()
  if (!offline) return null
  return (
    <div role="alert" className="border-b border-rejected/30 bg-rejected-soft text-rejected">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-sm">
        <WifiOff className="size-4 shrink-0" aria-hidden />
        <span>
          Can't reach the backend at <span className="font-mono">{API_URL}</span>. Start it with{" "}
          <span className="font-mono">uvicorn app.main:app --reload</span> in the backend folder.
        </span>
      </div>
    </div>
  )
}

export function Layout() {
  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-20 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <CircleCheckBig className="size-5 text-primary" aria-hidden />
            <span>Vendor Onboarding</span>
          </NavLink>
          <nav className="ml-2 flex items-center gap-1" aria-label="Main">
            <NavItem to="/" icon={LayoutDashboard} label="Dashboard" />
            <NavItem to="/submit" icon={FilePlus2} label="New submission" />
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <ModeBadge />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <OfflineBanner />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
