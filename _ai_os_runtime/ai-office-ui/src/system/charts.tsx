/**
 * AI Investment OS — Chart Wrappers (recharts)
 *
 * Themed recharts components that consume our semantic CSS variables so they
 * adapt to light/dark automatically. Replaces the old UI which had zero
 * charts despite dense numeric data.
 *
 * Note: recharts reads colors from props, not CSS vars at render time for
 * SVG fills. We bridge by reading the computed CSS variable via a hook.
 */

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Treemap as RTreemap,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  type TooltipProps,
} from "recharts";
import { useUIStore } from "../store";

/** Read a CSS custom property from :root (live, theme-aware). */
function useCssVar(name: string): string {
  const theme = useUIStore((s) => s.theme);
  const [value, setValue] = React.useState("");
  React.useEffect(() => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    setValue(v);
  }, [theme, name]);
  return value;
}

/** Themed tooltip content for recharts. */
function ThemedTooltip(props: TooltipProps<number, string>) {
  const { active, payload, label } = props as {
    active?: boolean;
    payload?: Array<{ name?: string; value?: number | string; color?: string }>;
    label?: string | number;
  };
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-sm)",
      padding: "var(--space-2) var(--space-3)",
      boxShadow: "var(--shadow-3)",
      fontSize: "var(--text-sm)",
    }}>
      {label !== undefined && (
        <div style={{ color: "var(--text-muted)", marginBottom: 4, fontWeight: 500 }}>{label}</div>
      )}
      {payload.map((entry: { name?: string; value?: number | string; color?: string }, i: number) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: entry.color }} />
          <span style={{ color: "var(--text)" }}>
            {entry.name}: <strong style={{ fontVariantNumeric: "tabular-nums" }}>{entry.value}</strong>
          </span>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
 * SPARKLINE — tiny inline trend (no axes)
 * ============================================================ */
export interface SparklineProps {
  data: Array<{ value: number; label?: string }>;
  color?: string;
  height?: number;
  width?: number;
}
export function Sparkline({ data, color, height = 32, width = 100 }: SparklineProps) {
  const accent = useCssVar("--accent") || "#0f766e";
  const stroke = color || accent;
  if (!data || data.length === 0) return <div style={{ height, width }} />;
  return (
    <ResponsiveContainer width={width} height={height}>
      <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id="aios-spark" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.3} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="value" stroke={stroke} strokeWidth={1.5} fill="url(#aios-spark)" isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ============================================================
 * AREA CHART — full trend with axes
 * ============================================================ */
export interface AreaSeriesChartProps {
  data: Array<Record<string, number | string>>;
  series: Array<{ key: string; name: string; color?: string }>;
  xKey: string;
  height?: number;
  yFormat?: (v: number) => string;
}
export function AreaSeriesChart({ data, series, xKey, height = 240, yFormat }: AreaSeriesChartProps) {
  const accent = useCssVar("--accent");
  const grid = useCssVar("--border-subtle");
  const muted = useCssVar("--text-muted");
  const palette = [accent, "#2d7a4f", "#d4a028", "#5b6b7a", "#6d4a8a"];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
        <defs>
          {series.map((s, i) => {
            const c = s.color || palette[i % palette.length];
            return (
              <linearGradient key={s.key} id={`aios-area-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c} stopOpacity={0.25} />
                <stop offset="100%" stopColor={c} stopOpacity={0} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke={grid || "#e3ddd2"} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={yFormat} width={56} />
        <RTooltip content={<ThemedTooltip />} />
        {series.map((s, i) => (
          <Area
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color || palette[i % palette.length]}
            strokeWidth={2}
            fill={`url(#aios-area-${s.key})`}
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ============================================================
 * LINE CHART
 * ============================================================ */
export interface LineSeriesChartProps {
  data: Array<Record<string, number | string>>;
  series: Array<{ key: string; name: string; color?: string }>;
  xKey: string;
  height?: number;
}
export function LineSeriesChart({ data, series, xKey, height = 240 }: LineSeriesChartProps) {
  const accent = useCssVar("--accent");
  const grid = useCssVar("--border-subtle");
  const muted = useCssVar("--text-muted");
  const palette = [accent, "#2d7a4f", "#d4a028", "#5b6b7a", "#6d4a8a"];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={grid || "#e3ddd2"} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
        <RTooltip content={<ThemedTooltip />} />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.color || palette[i % palette.length]}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ============================================================
 * BAR CHART
 * ============================================================ */
export interface BarSeriesChartProps {
  data: Array<Record<string, number | string>>;
  bars: Array<{ key: string; name: string; color?: string }>;
  xKey: string;
  height?: number;
  stacked?: boolean;
}
export function BarSeriesChart({ data, bars, xKey, height = 240, stacked }: BarSeriesChartProps) {
  const accent = useCssVar("--accent");
  const grid = useCssVar("--border-subtle");
  const muted = useCssVar("--text-muted");
  const palette = [accent, "#2d7a4f", "#d4a028", "#5b6b7a", "#6d4a8a"];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
        <CartesianGrid strokeDasharray="2 4" stroke={grid || "#e3ddd2"} vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
        <RTooltip content={<ThemedTooltip />} cursor={{ fill: "var(--surface-soft)" }} />
        {bars.map((b, i) => (
          <Bar
            key={b.key}
            dataKey={b.key}
            name={b.name}
            stackId={stacked ? "a" : undefined}
            fill={b.color || palette[i % palette.length]}
            radius={stacked ? 0 : [3, 3, 0, 0]}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ============================================================
 * DONUT — allocation / composition
 * ============================================================ */
export interface DonutChartProps {
  data: Array<{ name: string; value: number; color?: string }>;
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
}
export function DonutChart({ data, height = 220, innerRadius = 50, outerRadius = 80 }: DonutChartProps) {
  const palette = ["#0f766e", "#2d7a4f", "#d4a028", "#5b6b7a", "#6d4a8a", "#c0392b", "#14b8a6", "#7a4800"];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <RTooltip content={<ThemedTooltip />} />
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={innerRadius}
          outerRadius={outerRadius}
          paddingAngle={2}
          isAnimationActive={false}
        >
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.color || palette[i % palette.length]} stroke="var(--surface)" strokeWidth={2} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}

/* ============================================================
 * TREEMAP — exposure / allocation
 * ============================================================ */
export interface TreemapProps {
  data: Array<{ name: string; value: number; color?: string }>;
  height?: number;
}
export function Treemap({ data, height = 280 }: TreemapProps) {
  const palette = ["#0f766e", "#2d7a4f", "#d4a028", "#5b6b7a", "#6d4a8a", "#c0392b", "#14b8a6", "#7a4800"];
  const chartData = data.map((d, i) => ({ ...d, fill: d.color || palette[i % palette.length] }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RTreemap
        data={chartData}
        dataKey="value"
        nameKey="name"
        stroke="var(--surface)"
        isAnimationActive={false}
        content={<TreemapContent />}
      />
    </ResponsiveContainer>
  );
}

function TreemapContent(props: unknown) {
  const { x, y, width, height, name, value, fill } = props as {
    x: number; y: number; width: number; height: number; name: string; value: number; fill: string;
  };
  if (width < 30 || height < 20) return null;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} fillOpacity={0.85} stroke="var(--surface)" strokeWidth={2} rx={4} />
      <text x={x + 6} y={y + 16} fill="#fff" fontSize={11} fontWeight={600}>
        {String(name).slice(0, 12)}
      </text>
      {height > 36 && (
        <text x={x + 6} y={y + 30} fill="#fff" fontSize={10} opacity={0.85}>
          {value}
        </text>
      )}
    </g>
  );
}

/* ============================================================
 * MINI BAR — tiny horizontal bar (for inline comparisons)
 * ============================================================ */
export function MiniBar({ value, max, color, height = 6 }: { value: number; max: number; color?: string; height?: number }) {
  const accent = useCssVar("--accent") || "#0f766e";
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div style={{
      width: "100%",
      height,
      background: "var(--bg-sunken)",
      borderRadius: "var(--radius-pill)",
      overflow: "hidden",
    }}>
      <div style={{
        width: `${pct}%`,
        height: "100%",
        background: color || accent,
        borderRadius: "var(--radius-pill)",
        transition: "width var(--duration-base) var(--ease-out)",
      }} />
    </div>
  );
}
