import { Check, FilePlus2, LayoutDashboard, Menu, WifiOff, X } from "lucide-react"
import { useState } from "react"
import { NavLink, Outlet, useNavigate } from "react-router"

import { ResetDemo } from "@/components/ResetDemo"
import { ThemeToggle } from "@/components/ThemeToggle"
import { Button } from "@/components/ui/button"
import { useHealth } from "@/hooks/useHealth"
import { API_URL } from "@/lib/api"
import { cn } from "@/lib/utils"

// Shared look of a sidebar item. The active one is red with a 3px red bar on its left edge.
const ITEM =
  "relative flex items-center gap-2.5 px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"

function NavItem({ to, icon: Icon, label, onClick }: {
  to: string; icon: typeof LayoutDashboard; label: string; onClick: () => void
}) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      onClick={onClick}
      className={({ isActive }) =>
        cn(ITEM, isActive && "bg-background font-semibold text-brand before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-primary")
      }
    >
      <Icon className="size-4" aria-hidden />
      {label}
    </NavLink>
  )
}

function ExtractorLabel() {
  const { health } = useHealth()
  if (!health) return null
  const gemini = health.extractor_mode === "gemini"
  return (
    <span
      className="hidden text-xs text-muted-foreground sm:inline"
      title={gemini ? "Documents are read by Gemini" : "Documents are read by the offline mock extractor"}
    >
      Extractor: <span className="font-medium text-foreground">{gemini ? "Gemini" : "Mock"}</span>
    </span>
  )
}

function OfflineBanner() {
  const { offline } = useHealth()
  if (!offline) return null
  return (
    <div role="alert" className="border-b border-rejected bg-rejected-soft text-rejected">
      <div className="flex items-center gap-2 px-4 py-2 text-sm">
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
  const { health } = useHealth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [epoch, setEpoch] = useState(0) // bumped after a demo reset so the page reloads its data
  const close = () => setMenuOpen(false)

  return (
    <div className="min-h-svh bg-background">
      <div className="h-0.5 bg-primary" aria-hidden />
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background px-4">
        <Button
          variant="ghost" size="icon" className="lg:hidden" onClick={() => setMenuOpen((o) => !o)}
          aria-label={menuOpen ? "Close menu" : "Open menu"} aria-expanded={menuOpen} aria-controls="sidebar"
        >
          {menuOpen ? <X className="size-4" /> : <Menu className="size-4" />}
        </Button>
        <NavLink to="/" className="flex items-center gap-2.5 font-semibold text-foreground" onClick={close}>
          <span className="flex size-5 items-center justify-center rounded-sm bg-primary text-primary-foreground">
            <Check className="size-3.5" strokeWidth={3} aria-hidden />
          </span>
          Vendor Onboarding
        </NavLink>
        <div className="ml-auto flex items-center gap-3">
          <ExtractorLabel />
          <ThemeToggle />
        </div>
      </header>
      <OfflineBanner />
      <div className="flex">
        <aside
          id="sidebar"
          className={cn(
            "z-20 w-56 shrink-0 border-r bg-sidebar",
            // on narrow screens the sidebar is a menu that opens over the page
            menuOpen ? "fixed top-[58px] bottom-0 left-0 block overflow-y-auto" : "hidden",
            "lg:sticky lg:top-[58px] lg:block lg:h-[calc(100svh-58px)] lg:self-start lg:overflow-y-auto",
          )}
        >
          <nav className="py-3" aria-label="Main">
            <NavItem to="/" icon={LayoutDashboard} label="Dashboard" onClick={close} />
            <NavItem to="/submit" icon={FilePlus2} label="New submission" onClick={close} />
            {health?.demo_mode && (
              <div className="mt-4 border-t pt-3">
                <div className="px-4 pb-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Demo</div>
                <ResetDemo
                  itemClass={ITEM}
                  onDone={() => { close(); navigate("/"); setEpoch((n) => n + 1) }}
                />
              </div>
            )}
          </nav>
        </aside>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6">
          <div className="max-w-[1280px]" key={epoch}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
