import type { ReactNode } from "react"

import { Panel } from "@/components/Panel"

/** A titled, bordered panel on the result page. */
export function Section({ title, description, children, className, action, flush }: {
  title: ReactNode; description?: ReactNode; icon?: ReactNode; children: ReactNode; className?: string
  action?: ReactNode; flush?: boolean
}) {
  return <Panel title={title} description={description} action={action} className={className} flush={flush}>{children}</Panel>
}
