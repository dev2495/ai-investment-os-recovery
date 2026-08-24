import React from "react";
import { NavLink } from "react-router-dom";
import { BookOpen, Library, Radar, Radio, Workflow } from "lucide-react";

const RESEARCH_NAV = [
  { to: "/research/desk", label: "Desk", icon: BookOpen, end: true },
  { to: "/research/cases", label: "Workstreams", icon: Workflow, end: false },
  { to: "/research/following", label: "Following", icon: Radio, end: false },
  { to: "/research/scanners", label: "Fundamental scanners", icon: Radar, end: false },
  { to: "/research/knowledge", label: "Knowledge", icon: Library, end: false },
] as const;

export function ResearchDeskNav() {
  return (
    <nav className="rd-nav" aria-label="Company Research">
      {RESEARCH_NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) => "rd-nav__item " + (isActive ? "is-active" : "")}
        >
          <Icon size={15} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
