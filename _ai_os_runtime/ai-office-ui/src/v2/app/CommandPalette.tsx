/**
 * Command Palette (Cmd-K)
 *
 * Global, from anywhere:
 *   - Navigate: jump to any destination
 *   - Actions: toggle theme, open assistant, focus a 3D office room
 *   - Ask Charlie: type a question → routes to the assistant chat
 *
 * Built on cmdk (the shadcn/raycast-style primitive).
 */

import React from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import {
  Search,
  LayoutDashboard,
  Briefcase,
  FlaskConical,
  ShieldAlert,
  Building2,
  Sun,
  Moon,
  Sparkles,
  CornerDownLeft,
  Brain,
  BarChart3,
  BookOpen,
  TrendingUp,
  Newspaper,
  Gavel,
  ShieldCheck,
  Server,
  Database,
  Library,
} from "lucide-react";
import { useUIStore } from "../store";
import { DESTINATIONS } from "./destinations";
import { CommandPaletteCss } from "./CommandPalette.css";

const DEST_ICONS = { LayoutDashboard, Briefcase, FlaskConical, ShieldAlert, Building2 } as const;

export function CommandPalette() {
  const open = useUIStore((s) => s.paletteOpen);
  const setOpen = useUIStore((s) => s.setPaletteOpen);
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const focusRoom = useUIStore((s) => s.focusRoom);
  const pushToast = useUIStore((s) => s.pushToast);

  const navigate = useNavigate();
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  // Focus input when opened
  React.useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Esc closes (cmdk handles this internally but we sync store)
  React.useEffect(() => {
    if (!open) return;
    function onDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onDown);
    return () => window.removeEventListener("keydown", onDown);
  }, [open, setOpen]);

  if (!open) return null;

  /** Send a question to Charlie via the palette. */
  function askCharlie(question: string) {
    if (!question.trim()) return;
    setAssistantScope("charlie");
    setAssistantOpen(true);
    // Stash the question for the AssistantRail to pick up
    sessionStorage.setItem("aios:pending-charlie-question", question);
    setOpen(false);
    pushToast({
      title: "Asked Charlie",
      message: question.length > 60 ? `${question.slice(0, 60)}…` : question,
      tone: "info",
      duration: 2500,
    });
  }

  function go(path: string) {
    navigate(path);
    setOpen(false);
  }

  return (
    <>
      <style>{CommandPaletteCss}</style>
      <div className="aios-palette-overlay" onClick={() => setOpen(false)} />
      <Command.Dialog
        className="aios-palette"
        open={open}
        onOpenChange={setOpen}
        label="Command Palette"
      >
        <div className="aios-palette__input-wrap">
          <Search size={16} className="aios-palette__input-icon" />
          <Command.Input ref={inputRef} placeholder="Search, navigate, or ask Charlie…" className="aios-palette__input" />
          <kbd className="aios-palette__esc">ESC</kbd>
        </div>
        <Command.List className="aios-palette__list">
          <Command.Empty className="aios-palette__empty">No results found.</Command.Empty>

          {/* Navigate */}
          <Command.Group heading="Navigate" className="aios-palette__group">
            {DESTINATIONS.map((dest) => {
              const Icon = DEST_ICONS[dest.icon.displayName as keyof typeof DEST_ICONS] ?? dest.icon;
              return (
                <Command.Item
                  key={dest.key}
                  value={`go ${dest.label} ${dest.short} ${dest.description}`}
                  onSelect={() => go(dest.path)}
                  className="aios-palette__item"
                >
                  <Icon size={15} />
                  <span className="aios-palette__item-label">{dest.label}</span>
                  <span className="aios-palette__item-desc">{dest.description}</span>
                  <CornerDownLeft size={12} className="aios-palette__item-arrow" />
                </Command.Item>
              );
            })}
          </Command.Group>

          {/* Actions */}
          <Command.Group heading="Actions" className="aios-palette__group">
            <Command.Item
              value="toggle theme dark light mode"
              onSelect={() => { toggleTheme(); setOpen(false); }}
              className="aios-palette__item"
            >
              {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
              <span className="aios-palette__item-label">Switch to {theme === "light" ? "dark" : "light"} theme</span>
            </Command.Item>
            <Command.Item
              value="open charlie assistant chat"
              onSelect={() => { setAssistantScope("charlie"); setAssistantOpen(true); setOpen(false); }}
              className="aios-palette__item"
            >
              <Sparkles size={15} />
              <span className="aios-palette__item-label">Open Charlie assistant</span>
            </Command.Item>
            <Command.Item
              value="open 3d office firm floor walk"
              onSelect={() => { focusRoom(null); go("/firm/office"); }}
              className="aios-palette__item"
            >
              <Building2 size={15} />
              <span className="aios-palette__item-label">Walk the 3D office</span>
            </Command.Item>
          </Command.Group>

          {/* Quick rooms (3D office deep-links) */}
          <Command.Group heading="Jump to room" className="aios-palette__group">
            {OFFICE_ROOMS.map((room) => (
              <Command.Item
                key={room.key}
                value={`room ${room.label} ${room.department}`}
                onSelect={() => { focusRoom(room.key); go("/firm/office"); }}
                className="aios-palette__item"
              >
                <room.icon size={15} />
                <span className="aios-palette__item-label">{room.label}</span>
                <span className="aios-palette__item-desc">{room.department}</span>
              </Command.Item>
            ))}
          </Command.Group>

          {/* Ask Charlie — appears when query looks like a question */}
          <Command.Group heading="Ask Charlie" className="aios-palette__group">
            <Command.Item
              value="ask charlie question"
              onSelect={(val) => askCharlie(val.replace(/^ask\s+charlie\s*/i, ""))}
              className="aios-palette__item aios-palette__item--charlie"
            >
              <Sparkles size={15} />
              <span className="aios-palette__item-label">Ask Charlie: "<span className="aios-palette__charlie-q" />"</span>
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command.Dialog>
    </>
  );
}

/** The office rooms (kept in sync with office3d/rooms). */
const OFFICE_ROOMS = [
  { key: "lobby", label: "Lobby", department: "Today's brief screen", icon: LayoutDashboard },
  { key: "research", label: "Research Desk", department: "Research, Filings, Special Situations", icon: BookOpen },
  { key: "quant", label: "Quant Lab", department: "Strategy, Backtest, Validation, Optimizer", icon: BarChart3 },
  { key: "portfolio", label: "Portfolio Mgmt", department: "PM, Books, Positions", icon: Briefcase },
  { key: "trading", label: "Trading Desk", department: "TradingView, Blotter", icon: TrendingUp },
  { key: "news", label: "News Desk", department: "News, Social, Corporate Actions", icon: Newspaper },
  { key: "executive", label: "Executive Office", department: "Charlie Munger, Chief of Staff", icon: Brain },
  { key: "committee", label: "Committee Room", department: "Packets, positions, synthesis, votes", icon: Gavel },
  { key: "risk", label: "Risk & Compliance", department: "Risk Agent, limits, breaches", icon: ShieldCheck },
  { key: "runtime", label: "Runtime (basement)", department: "Jarvis, server racks", icon: Server },
  { key: "data", label: "Data Engineering", department: "Data Steward, pipelines", icon: Database },
  { key: "library", label: "Knowledge/Library", department: "Librarian, Obsidian vault", icon: Library },
] as const;
