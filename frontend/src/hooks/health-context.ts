import { createContext } from "react"

import type { Health } from "@/lib/api"

export interface HealthState {
  health: Health | null
  offline: boolean
}

export const HealthContext = createContext<HealthState>({ health: null, offline: false })
