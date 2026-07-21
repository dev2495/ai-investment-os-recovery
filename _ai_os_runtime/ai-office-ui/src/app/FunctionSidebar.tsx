/**
 * Function Sidebar (left rail)
 *
 * The Bloomberg-style "function keyboard". All terminal functions grouped
 * by domain. Each item shows its mnemonic code, label, and status dot.
 * Collapses to icons on narrow screens.
 */

import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { FUNCTION_GROUPS, functionsForGroup, functionForPath } from "./destinations";

export function FunctionSidebar() {
  const location = useLocation();
  const activeFn = functionForPath(location.pathname);

  // Collapse state per group (persisted in memory)
  const [collapsed, setCollapsed] = React.useState<Set<string>>(React.useMemo(() => new Set(["macro", "research", "risk"]), []));

  function toggle(group: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  }

  return (
    <aside className="aios-sidebar" aria-label="Terminal functions">
      <div className="aios-sidebar__scroll">
        {FUNCTION_GROUPS.map((group) => {
          const fns = functionsForGroup(group.key);
          if (fns.length === 0) return null;
          const isCollapsed = collapsed.has(group.key);
          return (
            <div key={group.key} className="aios-sidebar__group">
              <button
                className="aios-sidebar__group-head"
                onClick={() => toggle(group.key)}
                style={{ width: "100%", cursor: "pointer" }}
              >
                <group.icon size={12} />
                <span style={{ flex: 1, textAlign: "left" }}>{group.label}</span>
                <ChevronDown
                  size={11}
                  style={{
                    transition: "transform var(--duration-fast)",
                    transform: isCollapsed ? "rotate(-90deg)" : "rotate(0)",
                  }}
                />
              </button>
              {!isCollapsed && fns.map((fn) => {
                const isActive = activeFn?.path === fn.path;
                return (
                  <NavLink
                    key={fn.path}
                    to={fn.path}
                    className={`aios-sidebar__item ${isActive ? "aios-sidebar__item--active" : ""}`}
                    title={fn.description}
                  >
                    <span className="aios-sidebar__item-icon">
                      <fn.icon size={14} />
                    </span>
                    <span className="aios-sidebar__item-label">{fn.label}</span>
                    <span className={`aios-sidebar__item-status aios-sidebar__item-status--${fn.status ?? "beta"}`} />
                    <span className="aios-sidebar__item-code">{fn.code}</span>
                  </NavLink>
                );
              })}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
