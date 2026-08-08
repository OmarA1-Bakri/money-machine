export type ServiceState = "healthy" | "unverified";

export interface ServiceStatus {
  readonly name: string;
  readonly state: ServiceState;
  readonly detail: string;
}

export const serviceStatuses = [
  {
    name: "Operator console",
    state: "healthy",
    detail: "This page rendered successfully.",
  },
  {
    name: "API",
    state: "unverified",
    detail: "No API connection is configured in this bootstrap build.",
  },
  {
    name: "PostgreSQL",
    state: "unverified",
    detail: "Database health is not queried by the web application.",
  },
  {
    name: "Worker",
    state: "unverified",
    detail: "Worker state is not available in Session 00.",
  },
  {
    name: "Scheduler",
    state: "unverified",
    detail: "Scheduler state is not available in Session 00.",
  },
] as const satisfies readonly ServiceStatus[];

export const bootstrapSummary = {
  currentSession: 0,
  mode: "Bootstrap only",
  externalActions: false,
  businessTransitions: false,
} as const;
