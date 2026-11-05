import { useContext } from "react"

import { HealthContext } from "./health-context"

export const useHealth = () => useContext(HealthContext)
