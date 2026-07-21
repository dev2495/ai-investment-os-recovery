/**
 * AI Investment OS — Destinations Registry
 *
 * The 5 top-level destinations. Shared by the topbar nav, command palette,
 * and breadcrumbs. Collapses the old 20 overlapping workspaces into 5 clear
 * places.
 */

import {
  LayoutDashboard,
  Briefcase,
  FlaskConical,
  ShieldAlert,
  Building2,
  type LucideIcon,
} from "lucide-react";

export interface Destination {
  key: string;
  path: string;
  label: string;
  icon: LucideIcon;
  short: string; // for command palette
  description: string;
}

export const DESTINATIONS: Destination[] = [
  {
    key: "today",
    path: "/today",
    label: "Today",
    icon: LayoutDashboard,
    short: "today",
    description: "Daily brief, decisions, delegations, freshness",
  },
  {
    key: "portfolio",
    path: "/portfolio",
    label: "Portfolio",
    icon: Briefcase,
    short: "portfolio",
    description: "Clients, books, positions, accounting, reconciliation",
  },
  {
    key: "research",
    path: "/research",
    label: "Research & Strategy",
    icon: FlaskConical,
    short: "research",
    description: "Ideas, theses, filings, special situations, strategy lab, reports",
  },
  {
    key: "risk-trading",
    path: "/risk-trading",
    label: "Risk & Trading",
    icon: ShieldAlert,
    short: "risk",
    description: "Risk dashboard, limits, trading, quant, execution safety",
  },
  {
    key: "firm",
    path: "/firm",
    label: "The Firm",
    icon: Building2,
    short: "firm",
    description: "3D office, agents, departments, committees, governance, models, system",
  },
];

export function getDestination(key: string): Destination | undefined {
  return DESTINATIONS.find((d) => d.key === key);
}
