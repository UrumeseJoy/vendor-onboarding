import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** A bordered panel with a grey header row holding the title. The basic building block of every page. */
export function Panel({ title, description, action, children, className, bodyClassName, flush }: {
  title?: ReactNode; description?: ReactNode; action?: ReactNode; children: ReactNode
  className?: string; bodyClassName?: string; flush?: boolean // flush: no body padding (tables, lists)
}) {
  return (
    <section className={cn("overflow-hidden rounded-sm border bg-card text-card-foreground", className)}>
      {(title || action) && (
        <header className="flex min-h-10 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b bg-muted px-4 py-2">
          <div className="min-w-0">
            <h2 className="text-[15px] leading-6 font-semibold">{title}</h2>
            {description && <p className="text-xs text-muted-foreground">{description}</p>}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </header>
      )}
      <div className={cn(!flush && "p-4", bodyClassName)}>{children}</div>
    </section>
  )
}

/** A label above a value. Used in key-facts bands and summaries. */
export function Fact({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{children}</dd>
    </div>
  )
}
