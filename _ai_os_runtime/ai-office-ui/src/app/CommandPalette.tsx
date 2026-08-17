/**
 * Command Palette (Cmd-K)
 *
 * Bloomberg-style: jump to any function by code (<PORT>, <QLAB>) or name,
 * run actions, or ask Charlie a question. Driven by the terminal function
 * registry so every screen is reachable from here.
 */

import React from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import {
  Search, Sun, Moon, Sparkles, CornerDownLeft,
  Brain, BookOpen, TrendingUp, Newspaper, Gavel, ShieldCheck, Server, Database, Library,
} from "lucide-react";
import { useUIStore } from "../store";
import { TERMINAL_FUNCTIONS, FUNCTION_GROUPS } from "./destinations";
import { CommandPaletteCss } from "./CommandPalette.css";

/** Office rooms (synced with office3d). */
const OFFICE_ROOMS = [
  { key: "lobby", label: "Lobby", department: "Today's brief screen" },
  { key: "research", label: "Research Desk", department: "Research, Filings, Special Situations" },
  { key: "quant", label: "Quant Lab", department: "Strategy, Backtest, Validation, Optimizer" },
  { key: "portfolio", label: "Portfolio Mgmt", department: "PM, Books, Positions" },
  { key: "trading", label: "Trading Desk", department: "TradingView, Blotter" },
  { key: "news", label: "News Desk", department: "News, Social, Corporate Actions" },
  { key: "executive", label: "Executive Office", department: "Charlie Munger, Chief of Staff" },
  { key: "committee", label: "Committee Room", department: "Packets, positions, synthesis, votes" },
  { key: "risk", label: "Risk & Compliance", department: "Risk Agent, limits, breaches" },
  { key: "runtime", label: "Runtime (basement)", department: "Jarvis, server racks" },
  { key: "data", label: "Data Engineering", department: "Data Steward, pipelines" },
  { key: "library", label: "Knowledge/Library", department: "Librarian, Obsidian vault" },
] as const;

const ROOM_ICONS: Record<string, typeof Sparkles> = {
  research: BookOpen,
  quant: Brain,
  trading: TrendingUp,
  news: Newspaper,
  committee: Gavel,
  risk: ShieldCheck,
  runtime: Server,
  data: Database,
  library: Library,
};

export function CommandPalette() {
  const open = useUIStore((s) => s.paletteOpen);
  const setOpen = useUIStore((s) => s.setPaletteOpen);
  const theme = useUIStore((s) => s.theme);
  const toggleTheme = useUIStore((s) => s.toggleTheme);
  const setAssistantOpen = useUIStore((s) => s.setAssistantOpen);
  const queueAssistantMessage = useUIStore((s) => s.queueAssistantMessage);
  const setAssistantScope = useUIStore((s) => s.setAssistantScope);
  const focusRoom = useUIStore((s) => s.focusRoom);
  const pushToast = useUIStore((s) => s.pushToast);
  const navigate = useNavigate();

  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [query, setQuery] = React.useState("");

  React.useEffect(() => {
    if (open) { setQuery(""); requestAnimationFrame(() => inputRef.current?.focus()); }
  }, [open]);

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

  function askCharlie(question: string) {
    if (!question.trim()) return;
    setAssistantScope("charlie");
    queueAssistantMessage(question);
    setOpen(false);
    pushToast({ title: "Asked Charlie", message: question.length > 60 ? `${question.slice(0, 60)}…` : question, tone: "info", duration: 2500 });
  }

  function go(path: string) {
    navigate(path);
    setOpen(false);
  }

  return (
    <>
      <style>{CommandPaletteCss}</style>
      <div className="aios-palette-overlay" onClick={() => setOpen(false)} />
      <Command.Dialog className="aios-palette" open={open} onOpenChange={setOpen} label="Command Palette">
        <div className="aios-palette__input-wrap">
          <Search size={16} className="aios-palette__input-icon" />
          <Command.Input ref={inputRef} value={query} onValueChange={setQuery} placeholder="Jump to function (<PORT>), search, or ask Charlie…" className="aios-palette__input" />
          <kbd className="aios-palette__esc">ESC</kbd>
        </div>
        <Command.List className="aios-palette__list">
          <Command.Empty className="aios-palette__empty">No results — try a function code like PORT, QLAB, or TODAY.</Command.Empty>

          {/* Terminal functions by group */}
          {FUNCTION_GROUPS.map((group) => {
            const fns = TERMINAL_FUNCTIONS.filter((f) => f.group === group.key);
            if (fns.length === 0) return null;
            return (
              <Command.Group key={group.key} heading={group.label} className="aios-palette__group">
                {fns.map((fn) => (
                  <Command.Item
                    key={fn.path}
                    value={`${fn.code} ${fn.label} ${fn.description} ${group.label}`}
                    onSelect={() => go(fn.path)}
                    className="aios-palette__item"
                  >
                    <fn.icon size={15} />
                    <span className="aios-palette__item-label">{fn.label}</span>
                    <span className="aios-palette__item-code">{fn.code}</span>
                    <CornerDownLeft size={12} className="aios-palette__item-arrow" />
                  </Command.Item>
                ))}
              </Command.Group>
            );
          })}

          {/* Actions */}
          <Command.Group heading="Actions" className="aios-palette__group">
            <Command.Item value="toggle theme dark light mode" onSelect={() => { toggleTheme(); setOpen(false); }} className="aios-palette__item">
              {theme === "light" ? <Moon size={15} /> : <Sun size={15} />}
              <span className="aios-palette__item-label">Switch to {theme === "light" ? "dark" : "light"} theme</span>
            </Command.Item>
            <Command.Item value="open charlie assistant chat" onSelect={() => { setAssistantScope("charlie"); setAssistantOpen(true); setOpen(false); }} className="aios-palette__item">
              <Sparkles size={15} />
              <span className="aios-palette__item-label">Open Charlie assistant</span>
            </Command.Item>
          </Command.Group>

          {/* Office rooms */}
          <Command.Group heading="Jump to room (3D office)" className="aios-palette__group">
            {OFFICE_ROOMS.map((room) => {
              const Icon = ROOM_ICONS[room.key] ?? Sparkles;
              return (
                <Command.Item
                  key={room.key}
                  value={`room ${room.label} ${room.department} office`}
                  onSelect={() => { focusRoom(room.key); go("/firm/office"); }}
                  className="aios-palette__item"
                >
                  <Icon size={15} />
                  <span className="aios-palette__item-label">{room.label}</span>
                  <span className="aios-palette__item-desc">{room.department}</span>
                </Command.Item>
              );
            })}
          </Command.Group>

          {/* Ask Charlie */}
          <Command.Group heading="Ask Charlie" className="aios-palette__group">
            <Command.Item
              value={"ask charlie "+query}
              onSelect={() => askCharlie(query)}
              className="aios-palette__item aios-palette__item--charlie"
            >
              <Sparkles size={15} />
              <span className="aios-palette__item-label">{query.trim() ? "Ask Charlie: “"+query.trim()+"”" : "Ask Charlie a question"}</span>
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command.Dialog>
    </>
  );
}
