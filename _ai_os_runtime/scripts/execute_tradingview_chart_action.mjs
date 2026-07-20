#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import zlib from "node:zlib";

const defaultArtifactRoot = "/Volumes/Devarsh SSD/AI OS Data/artifacts";

function parseArgs() {
  const args = process.argv.slice(2);
  const payloadIndex = args.indexOf("--payload-json");
  if (payloadIndex >= 0 && args[payloadIndex + 1]) {
    return JSON.parse(args[payloadIndex + 1]);
  }
  const payload = {};
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index]?.replace(/^--/, "").replace(/-([a-z])/g, (_, char) => char.toUpperCase());
    if (key) {
      payload[key] = args[index + 1];
    }
  }
  return payload;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function activateTradingViewDesktop(enabled) {
  if (!enabled || process.platform !== "darwin") {
    return enabled ? "native_activation_unsupported" : "native_activation_disabled";
  }
  const completed = spawnSync(
    "/usr/bin/osascript",
    ["-e", "tell application \"TradingView\" to activate"],
    { encoding: "utf8", timeout: 6000 }
  );
  if (completed.status !== 0) {
    const error = String(completed.stderr || completed.error?.message || "unknown error").trim();
    return `native_activation_failed:${error.slice(0, 180)}`;
  }
  return "native_activation_succeeded";
}

function slug(value) {
  return String(value || "tradingview-chart")
    .trim()
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 80) || "tradingview-chart";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

function normalizeSymbols(input) {
  if (Array.isArray(input)) {
    return input.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof input === "string") {
    return input.split(",").map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function parsePng(buffer) {
  const signature = "89504e470d0a1a0a";
  if (buffer.subarray(0, 8).toString("hex") !== signature) {
    throw new Error("Screenshot is not a PNG file");
  }
  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idatChunks = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.subarray(offset + 4, offset + 8).toString("ascii");
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    offset += 12 + length;
    if (type === "IHDR") {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") {
      idatChunks.push(data);
    } else if (type === "IEND") {
      break;
    }
  }
  if (bitDepth !== 8 || ![0, 2, 6].includes(colorType)) {
    throw new Error(`Unsupported PNG format: bitDepth=${bitDepth}, colorType=${colorType}`);
  }
  const channels = colorType === 6 ? 4 : colorType === 2 ? 3 : 1;
  const rowBytes = width * channels;
  const inflated = zlib.inflateSync(Buffer.concat(idatChunks));
  const pixels = Buffer.alloc(width * height * 4);
  let inputOffset = 0;
  let previous = Buffer.alloc(rowBytes);
  for (let y = 0; y < height; y += 1) {
    const filter = inflated[inputOffset];
    inputOffset += 1;
    const raw = Buffer.from(inflated.subarray(inputOffset, inputOffset + rowBytes));
    inputOffset += rowBytes;
    const recon = Buffer.alloc(rowBytes);
    for (let x = 0; x < rowBytes; x += 1) {
      const left = x >= channels ? recon[x - channels] : 0;
      const up = previous[x] || 0;
      const upLeft = x >= channels ? previous[x - channels] || 0 : 0;
      let value = raw[x];
      if (filter === 1) {
        value = (value + left) & 255;
      } else if (filter === 2) {
        value = (value + up) & 255;
      } else if (filter === 3) {
        value = (value + Math.floor((left + up) / 2)) & 255;
      } else if (filter === 4) {
        const p = left + up - upLeft;
        const pa = Math.abs(p - left);
        const pb = Math.abs(p - up);
        const pc = Math.abs(p - upLeft);
        const predictor = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
        value = (value + predictor) & 255;
      } else if (filter !== 0) {
        throw new Error(`Unsupported PNG filter: ${filter}`);
      }
      recon[x] = value;
    }
    for (let x = 0; x < width; x += 1) {
      const source = x * channels;
      const target = (y * width + x) * 4;
      if (colorType === 0) {
        pixels[target] = recon[source];
        pixels[target + 1] = recon[source];
        pixels[target + 2] = recon[source];
        pixels[target + 3] = 255;
      } else {
        pixels[target] = recon[source];
        pixels[target + 1] = recon[source + 1];
        pixels[target + 2] = recon[source + 2];
        pixels[target + 3] = colorType === 6 ? recon[source + 3] : 255;
      }
    }
    previous = recon;
  }
  return { width, height, pixels };
}

const crcTable = (() => {
  const table = new Uint32Array(256);
  for (let value = 0; value < 256; value += 1) {
    let crc = value;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc & 1) ? (0xedb88320 ^ (crc >>> 1)) : (crc >>> 1);
    table[value] = crc >>> 0;
  }
  return table;
})();

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function pngChunk(type, data) {
  const typeBuffer = Buffer.from(type, "ascii");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4);
  checksum.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])));
  return Buffer.concat([length, typeBuffer, data, checksum]);
}

function encodePng(width, height, pixels) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 6;
  const scanlines = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const target = y * (width * 4 + 1);
    scanlines[target] = 0;
    pixels.copy(scanlines, target + 1, y * width * 4, (y + 1) * width * 4);
  }
  return Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    pngChunk("IHDR", header),
    pngChunk("IDAT", zlib.deflateSync(scanlines, { level: 6 })),
    pngChunk("IEND", Buffer.alloc(0))
  ]);
}

function resizeNearest(image, width, height) {
  const pixels = Buffer.alloc(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    const sourceY = Math.min(image.height - 1, Math.floor(y * image.height / height));
    for (let x = 0; x < width; x += 1) {
      const sourceX = Math.min(image.width - 1, Math.floor(x * image.width / width));
      const source = (sourceY * image.width + sourceX) * 4;
      const target = (y * width + x) * 4;
      image.pixels.copy(pixels, target, source, source + 4);
    }
  }
  return { width, height, pixels };
}

function composeFourPanePng(paths) {
  const paneWidth = 960;
  const paneHeight = 540;
  const canvas = Buffer.alloc(paneWidth * 2 * paneHeight * 2 * 4, 18);
  paths.forEach((filePath, index) => {
    const pane = resizeNearest(parsePng(fs.readFileSync(filePath)), paneWidth, paneHeight);
    const offsetX = (index % 2) * paneWidth;
    const offsetY = Math.floor(index / 2) * paneHeight;
    for (let y = 0; y < paneHeight; y += 1) {
      const sourceStart = y * paneWidth * 4;
      const targetStart = ((offsetY + y) * paneWidth * 2 + offsetX) * 4;
      pane.pixels.copy(canvas, targetStart, sourceStart, sourceStart + paneWidth * 4);
    }
  });
  return encodePng(paneWidth * 2, paneHeight * 2, canvas);
}

function runFourPaneEvidenceBoard(payload) {
  const panes = Array.isArray(payload.panes) ? payload.panes.slice(0, 4) : [];
  if (panes.length !== 4 || panes.some((pane) => !pane?.url || !pane?.symbol)) {
    throw new Error("option straddle evidence board requires four validated pane URLs and symbols");
  }
  const artifactRoot = path.resolve(payload.artifact_root || payload.artifactRoot || process.env.AI_OS_ARTIFACT_ROOT || defaultArtifactRoot);
  const startedAt = new Date().toISOString();
  const paneResults = panes.map((pane, index) => {
    const childPayload = {
      ...payload,
      action: "open_chart_capture",
      panes: [],
      symbols: [pane.symbol],
      symbol: pane.symbol,
      target_url: pane.url,
      activate_app: index === 0 && payload.activate_app !== false,
      max_quality_attempts: Math.min(2, Number(payload.max_quality_attempts || 2)),
      wait_ms: Math.min(7000, Number(payload.wait_ms || 5000))
    };
    const child = spawnSync(process.execPath, [process.argv[1], "--payload-json", JSON.stringify(childPayload)], {
      encoding: "utf8",
      timeout: 90000,
      maxBuffer: 10 * 1024 * 1024
    });
    if (child.status !== 0) throw new Error(`pane ${pane.label || index + 1} failed: ${String(child.stderr || child.stdout).slice(0, 800)}`);
    const result = JSON.parse(child.stdout || "{}");
    if (!result.screenshot_path || !fs.existsSync(result.screenshot_path)) throw new Error(`pane ${pane.label || index + 1} produced no screenshot`);
    return { label: pane.label, symbol: pane.symbol, url: pane.url, ...result };
  });
  const dateFolder = new Date().toISOString().slice(0, 10).replaceAll("-", "");
  const artifactDir = path.join(artifactRoot, "tradingview", dateFolder);
  fs.mkdirSync(artifactDir, { recursive: true });
  const screenshotPath = path.join(artifactDir, `${new Date().toISOString().replace(/[:.]/g, "-")}-option-straddle-four-pane.png`);
  fs.writeFileSync(screenshotPath, composeFourPanePng(paneResults.map((result) => result.screenshot_path)));
  const allPassed = paneResults.every((result) => ["passed", "skipped", "not_checked"].includes(result.artifact_quality_status));
  return {
    status: allPassed ? "done" : "needs_review",
    action: "option_straddle_layout_request",
    action_dispatch_status: "passed",
    layout_mode: "four_chart_evidence_board",
    target_url: paneResults[3].target_url,
    page_url: paneResults[3].page_url,
    page_title: "TradingView option straddle four-chart evidence board",
    extracted_text_preview: paneResults.map((result) => `${result.label}: ${result.page_title || result.symbol}`).join(" | "),
    screenshot_path: screenshotPath,
    screenshot_bytes: fs.statSync(screenshotPath).size,
    artifact_quality_status: allPassed ? "passed" : "failed",
    artifact_quality: { status: allPassed ? "passed" : "failed", pane_count: paneResults.length },
    quality_attempts: paneResults.reduce((total, result) => total + Number(result.quality_attempts || 0), 0),
    chart_setup_actions: [{ action: "compose_four_chart_evidence_board", pane_count: paneResults.length }],
    study_results: [],
    study_application_status: "not_requested",
    quality_recovery_actions: [],
    cdp_target_id: paneResults[3].cdp_target_id,
    cdp_target_title: paneResults[3].cdp_target_title,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    symbols: panes.map((pane) => pane.symbol),
    exchange: payload.exchange || null,
    timeframe: payload.timeframe || null,
    chart_layout: payload.chart_layout || payload.chartLayout || "four_chart_evidence_board",
    chart_style: payload.chart_style || payload.chartStyle || "Line",
    pane_results: paneResults
  };
}

function analyzeScreenshotQuality(pngBuffer) {
  const { width, height, pixels } = parsePng(pngBuffer);
  const region = {
    x0: Math.max(60, Math.floor(width * 0.04)),
    y0: Math.max(130, Math.floor(height * 0.11)),
    x1: Math.min(Math.floor(width * 0.78), width - 380),
    y1: Math.min(Math.floor(height * 0.82), height - 150)
  };
  let sampled = 0;
  let saturated = 0;
  let chartLike = 0;
  let bright = 0;
  const step = 3;
  for (let y = region.y0; y < region.y1; y += step) {
    for (let x = region.x0; x < region.x1; x += step) {
      const idx = (y * width + x) * 4;
      const r = pixels[idx];
      const g = pixels[idx + 1];
      const b = pixels[idx + 2];
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      sampled += 1;
      if (max > 55) {
        bright += 1;
      }
      if (max > 70 && max - min > 45) {
        saturated += 1;
      }
      const redCandle = r > 120 && g < 110 && b < 110;
      const greenCandle = g > 110 && r < 120 && b < 140;
      const blueLine = b > 120 && r < 120 && g < 160;
      if (redCandle || greenCandle || blueLine) {
        chartLike += 1;
      }
    }
  }
  const saturated_ratio = sampled ? saturated / sampled : 0;
  const chart_like_ratio = sampled ? chartLike / sampled : 0;
  const bright_ratio = sampled ? bright / sampled : 0;
  const passed = chart_like_ratio >= 0.0014 || saturated_ratio >= 0.0022;
  return {
    status: passed ? "passed" : "failed",
    reason: passed ? "chart_pixels_detected" : "chart_canvas_likely_blank",
    width,
    height,
    region,
    sampled_pixels: sampled,
    saturated_pixels: saturated,
    chart_like_pixels: chartLike,
    bright_pixels: bright,
    saturated_ratio: Number(saturated_ratio.toFixed(6)),
    chart_like_ratio: Number(chart_like_ratio.toFixed(6)),
    bright_ratio: Number(bright_ratio.toFixed(6)),
    thresholds: {
      chart_like_ratio: 0.0014,
      saturated_ratio: 0.0022
    }
  };
}

function analyzePngFile(filePath) {
  return analyzeScreenshotQuality(fs.readFileSync(filePath));
}

function buildTradingViewUrl(payload) {
  const symbols = normalizeSymbols(payload.symbols);
  const exchange = String(payload.exchange || "NSE").trim().toUpperCase();
  const firstSymbol = String(payload.symbol || symbols[0] || "NIFTY").trim().toUpperCase();
  const fullSymbol = firstSymbol.includes(":") ? firstSymbol : `${exchange}:${firstSymbol}`;
  const params = new URLSearchParams();
  params.set("symbol", fullSymbol);
  if (payload.timeframe) {
    params.set("interval", String(payload.timeframe).trim());
  }
  return `https://www.tradingview.com/chart/?${params.toString()}`;
}

async function chooseTradingViewTarget(port, requestedTargetId = null) {
  const targets = await fetchJson(`http://127.0.0.1:${port}/json/list`);
  const pages = targets.filter((target) => target.type === "page" && target.webSocketDebuggerUrl);
  if (requestedTargetId) {
    const requested = pages.find((target) => target.id === requestedTargetId);
    if (!requested) {
      throw new Error(`Requested TradingView CDP target not found: ${requestedTargetId}`);
    }
    return requested;
  }
  const chart = pages.find((target) => String(target.url || "").startsWith("https://www.tradingview.com/chart"));
  const webPage = pages.find((target) => String(target.url || "").startsWith("https://www.tradingview.com"));
  const fallback = pages.find((target) => !String(target.url || "").startsWith("file:"));
  const target = chart || webPage || fallback || pages[0];
  if (!target) {
    throw new Error("No controllable TradingView page target found on CDP port");
  }
  return target;
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      if (!payload.id || !this.pending.has(payload.id)) {
        return;
      }
      const { resolve, reject } = this.pending.get(payload.id);
      this.pending.delete(payload.id);
      if (payload.error) {
        reject(new Error(`${payload.error.message || "CDP error"} (${payload.error.code || "no_code"})`));
      } else {
        resolve(payload.result || {});
      }
    });
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timed out connecting to TradingView CDP WebSocket")), 5000);
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      });
      this.ws.addEventListener("error", (event) => {
        clearTimeout(timer);
        reject(new Error(`CDP WebSocket error: ${event.message || "unknown"}`));
      });
    });
  }

  call(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for CDP method ${method}`));
      }, 20000);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        }
      });
    });
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

async function resetChartView(client) {
  await client.call("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Alt",
    code: "AltLeft",
    windowsVirtualKeyCode: 18,
    modifiers: 1
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "r",
    code: "KeyR",
    windowsVirtualKeyCode: 82,
    modifiers: 1
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "r",
    code: "KeyR",
    windowsVirtualKeyCode: 82,
    modifiers: 1
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Alt",
    code: "AltLeft",
    windowsVirtualKeyCode: 18,
    modifiers: 0
  });
  return "reset_chart_alt_r";
}

async function enableAutoScale(client) {
  const candidate = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const nodes = [...document.querySelectorAll('button,[role="button"],[role="menuitem"],[data-role="menuitem"],[role="tab"],[data-role="tab"],[role="dialog"] *')];
      const candidates = nodes.map((item) => {
        const label = [item.getAttribute('aria-label'), item.getAttribute('title'), item.textContent]
          .filter(Boolean).join(' ').toLowerCase();
        const rect = item.getBoundingClientRect();
        return { item, label, rect };
      }).filter(({ label, rect }) => label.includes('auto scale') && rect.width > 0 && rect.height > 0)
        .sort((left, right) => right.rect.right - left.rect.right);
      const node = candidates[0]?.item;
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      return {
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
        pressed: node.getAttribute('aria-pressed'),
        label: node.getAttribute('aria-label') || node.getAttribute('title') || node.textContent
      };
    })()`,
    returnByValue: true
  });
  const value = candidate.result?.value;
  if (!value) {
    return "auto_scale_control_not_found";
  }
  if (String(value.pressed).toLowerCase() === "true") {
    return "auto_scale_already_enabled";
  }
  await client.call("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: value.x,
    y: value.y,
    button: "left",
    clickCount: 1
  });
  await client.call("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: value.x,
    y: value.y,
    button: "left",
    clickCount: 1
  });
  return `enabled_auto_scale:${String(value.label || "control").trim()}`;
}

async function readSeriesState(client) {
  const state = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const text = document.body?.innerText || '';
      const missingOhlc = /\nO\n(?:∅|--|N\/A)\nH\n(?:∅|--|N\/A)\nL\n(?:∅|--|N\/A)\nC\n(?:∅|--|N\/A)/i.test(text);
      const controls = [...document.querySelectorAll('button,[role="button"]')]
        .map((item) => {
          const rect = item.getBoundingClientRect();
          const label = [item.getAttribute('aria-label'), item.getAttribute('title'), item.textContent]
            .filter(Boolean).join(' ').trim();
          return { label, width: rect.width, height: rect.height };
        })
        .filter((item) => item.width > 0 && item.height > 0 && /show|hide|series|symbol|candle|auto scale/i.test(item.label))
        .slice(0, 40);
      return { missing_ohlc: missingOhlc, controls };
    })()`,
    returnByValue: true
  });
  return state.result?.value || { missing_ohlc: null, controls: [] };
}

async function hoverMainSeriesRow(client) {
  const candidate = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const title = [...document.querySelectorAll('span[class*="title-"][class*="main-"]')].find((item) =>
        /(NSE|BSE|NASDAQ|NYSE)/i.test((item.innerText || '').trim()) && (item.innerText || '').trim().length < 100
      );
      if (!title) return null;
      let row = title;
      for (let depth = 0; row && depth < 6; depth += 1, row = row.parentElement) {
        const rect = row.getBoundingClientRect();
        if (rect.width > 180 && rect.height >= 24 && rect.height <= 80) {
          return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width, height: rect.height };
        }
      }
      return null;
    })()`,
    returnByValue: true
  });
  const value = candidate.result?.value;
  if (!value) return "main_series_row_not_found";
  await client.call("Input.dispatchMouseEvent", { type: "mouseMoved", x: value.x, y: value.y });
  await sleep(700);
  return `main_series_row_hovered:${Math.round(value.width)}x${Math.round(value.height)}`;
}

async function openChartContextMenu(client) {
  const candidate = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const canvases = [...document.querySelectorAll('canvas')].map((item) => ({ item, rect: item.getBoundingClientRect() }))
        .filter(({ rect }) => rect.width > 400 && rect.height > 240)
        .sort((left, right) => right.rect.width * right.rect.height - left.rect.width * left.rect.height);
      const rect = canvases[0]?.rect;
      if (!rect) return null;
      return { x: rect.left + rect.width * 0.62, y: rect.top + rect.height * 0.42, width: rect.width, height: rect.height };
    })()`,
    returnByValue: true
  });
  const value = candidate.result?.value;
  if (!value) return "chart_canvas_not_found";
  await client.call("Input.dispatchMouseEvent", { type: "mousePressed", x: value.x, y: value.y, button: "right", clickCount: 1 });
  await client.call("Input.dispatchMouseEvent", { type: "mouseReleased", x: value.x, y: value.y, button: "right", clickCount: 1 });
  await sleep(700);
  return `chart_context_menu_opened:${Math.round(value.width)}x${Math.round(value.height)}`;
}

async function resetChartFromMenu(client) {
  const opened = await openChartContextMenu(client);
  if (!opened.startsWith("chart_context_menu_opened")) return opened;
  for (const label of ["Reset chart view", "Reset price scale"]) {
    const result = await clickNamedControl(client, label);
    if (!result.startsWith("control_not_found")) {
      await sleep(1200);
      return `${opened}:${result}`;
    }
  }
  await pressEscape(client);
  return `${opened}:reset_menu_item_not_found`;
}

async function clickPoint(client, value) {
  await client.call("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: value.x,
    y: value.y,
    button: "left",
    clickCount: 1
  });
  await client.call("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: value.x,
    y: value.y,
    button: "left",
    clickCount: 1
  });
}

async function clickNamedControl(client, requestedLabel) {
  const desired = String(requestedLabel || "").trim().toLowerCase();
  if (!desired) return "control_not_requested";
  const candidate = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const desired = ${JSON.stringify(desired)};
      const nodes = [...document.querySelectorAll('button,[role="button"],[role="menuitem"],[data-role="menuitem"],[role="tab"],[data-role="tab"]')];
      const candidates = nodes.map((item) => {
        const label = [item.getAttribute('aria-label'), item.getAttribute('title'), item.getAttribute('data-name'), item.textContent]
          .filter(Boolean).join(' ').trim().toLowerCase();
        const rect = item.getBoundingClientRect();
        const top = rect.width > 0 && rect.height > 0
          ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
          : null;
        return { item, label, rect, top, exact: label === desired, area: rect.width * rect.height };
      }).filter(({ item, label, rect, top }) => label.includes(desired) && rect.width > 0 && rect.height > 0 && top && item.contains(top))
        .sort((left, right) => Number(right.exact) - Number(left.exact) || left.area - right.area);
      const node = candidates[0]?.item;
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      node.click();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, label: node.getAttribute('aria-label') || node.getAttribute('title') || node.getAttribute('data-name') || node.textContent };
    })()`,
    returnByValue: true
  });
  const value = candidate.result?.value;
  if (!value) return `control_not_found:${slug(desired)}`;
  return `control_clicked:${slug(value.label || desired)}`;
}

async function closeDialogByName(client, dataName) {
  const desired = String(dataName || "").trim();
  if (!desired) return "dialog_not_requested";
  const result = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const dialog = document.querySelector('[role="dialog"][data-name=${JSON.stringify(desired)}]');
      if (!dialog) return { status: 'not_open' };
      const candidates = [...dialog.querySelectorAll('button,[role="button"],[data-role="button"],[aria-label],[title],[data-name]')]
        .map((item) => {
          const rect = item.getBoundingClientRect();
          const label = [item.getAttribute('aria-label'), item.getAttribute('title'), item.getAttribute('data-name')]
            .filter(Boolean).join(' ').trim().toLowerCase();
          return { item, rect, label };
        })
        .filter(({ rect, label }) => rect.width > 0 && rect.height > 0 && /close|cancel/.test(label))
        .sort((left, right) => Number(!left.label.includes('close')) - Number(!right.label.includes('close')));
      const control = candidates[0]?.item;
      if (!control) {
        const rect = dialog.getBoundingClientRect();
        return { status: 'close_not_found', x: rect.right - 38, y: rect.top + 38 };
      }
      control.click();
      return { status: 'closed', label: candidates[0].label };
    })()`,
    returnByValue: true
  });
  const value = result.result?.value || { status: "unknown" };
  if (value.status === "close_not_found") {
    if (Number.isFinite(value.x) && Number.isFinite(value.y)) {
      await clickPoint(client, value);
      await sleep(350);
      const afterClick = await client.call("Runtime.evaluate", {
        expression: `Boolean(document.querySelector('[role="dialog"][data-name=${JSON.stringify(desired)}]'))`,
        returnByValue: true
      });
      if (!afterClick.result?.value) {
        return `dialog_closed_by_geometry:${slug(desired)}`;
      }
    }
    await pressEscape(client);
    await sleep(350);
    const stillOpen = await client.call("Runtime.evaluate", {
      expression: `Boolean(document.querySelector('[role="dialog"][data-name=${JSON.stringify(desired)}]'))`,
      returnByValue: true
    });
    if (!stillOpen.result?.value) {
      return `dialog_closed_by_escape:${slug(desired)}`;
    }
  }
  await sleep(350);
  return `dialog_${value.status}:${slug(desired)}${value.label ? `:${slug(value.label)}` : ""}`;
}

async function clickDialogTab(client, dialogDataName, tabName) {
  const dialogName = String(dialogDataName || "").trim();
  const desired = String(tabName || "").trim().toLowerCase();
  const result = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const dialog = document.querySelector('[role="dialog"][data-name=${JSON.stringify(dialogName)}]');
      if (!dialog) return { status: 'dialog_not_open' };
      const tabs = [...dialog.querySelectorAll('button[role="tab"],[role="tab"]')]
        .map((item) => ({ item, text: (item.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase(), rect: item.getBoundingClientRect() }))
        .filter(({ rect }) => rect.width > 0 && rect.height > 0);
      const tab = tabs.find(({ text }) => text === ${JSON.stringify(desired)} || text === ${JSON.stringify(desired + desired)});
      if (!tab) return { status: 'tab_not_found', tabs: tabs.map(({ text }) => text) };
      tab.item.click();
      return { status: 'clicked', text: tab.text };
    })()`,
    returnByValue: true
  });
  const value = result.result?.value || { status: "unknown" };
  await sleep(500);
  return {
    action: "click_dialog_tab",
    dialog: dialogName,
    tab: desired,
    ...value
  };
}

async function clickDialogButton(client, dialogDataName, buttonName) {
  const dialogName = String(dialogDataName || "").trim();
  const desired = String(buttonName || "").trim().toLowerCase();
  const result = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const dialog = document.querySelector('[role="dialog"][data-name=${JSON.stringify(dialogName)}]');
      if (!dialog) return { status: 'dialog_not_open' };
      const controls = [...dialog.querySelectorAll('button,[role="button"],[data-role="button"]')]
        .map((item) => ({
          item,
          label: [item.getAttribute('aria-label'), item.getAttribute('title'), item.textContent]
            .filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim().toLowerCase(),
          rect: item.getBoundingClientRect()
        }))
        .filter(({ rect }) => rect.width > 0 && rect.height > 0);
      const control = controls.find(({ label }) => label === ${JSON.stringify(desired)} || label === ${JSON.stringify(desired + desired)});
      if (!control) return { status: 'button_not_found', controls: controls.map(({ label }) => label).filter(Boolean).slice(0, 30) };
      control.item.click();
      return { status: 'clicked', label: control.label };
    })()`,
    returnByValue: true
  });
  await sleep(500);
  return { action: "click_dialog_button", dialog: dialogName, button: desired, ...(result.result?.value || { status: "unknown" }) };
}

async function normalizeCandleVisibility(client) {
  const actions = [];
  actions.push(await closeDialogByName(client, "compare-dialog"));
  let settingsOpen = await client.call("Runtime.evaluate", {
    expression: "Boolean(document.querySelector('[role=\"dialog\"][data-name=\"series-properties-dialog\"]'))",
    returnByValue: true
  });
  if (!settingsOpen.result?.value) {
    actions.push(await clickNamedControl(client, "Settings"));
    await sleep(600);
    settingsOpen = await client.call("Runtime.evaluate", {
      expression: "Boolean(document.querySelector('[role=\"dialog\"][data-name=\"series-properties-dialog\"]'))",
      returnByValue: true
    });
  }
  if (!settingsOpen.result?.value) {
    return { action: "normalize_candle_visibility", status: "settings_dialog_not_open", actions };
  }
  actions.push(await clickDialogTab(client, "series-properties-dialog", "Symbol"));
  const normalized = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const dialog = document.querySelector('[role="dialog"][data-name="series-properties-dialog"]');
      const names = ['body', 'borders', 'wick'];
      return names.map((name) => {
        const label = [...dialog.querySelectorAll('label')].find((item) =>
          (item.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase() === name
        );
        if (!label) return { name, status: 'label_not_found' };
        const row = label.closest('[class*="cell-"]')?.parentElement || label.parentElement;
        const input = label.querySelector('input[type="checkbox"]') || row?.querySelector('input[type="checkbox"]');
        const before = input ? Boolean(input.checked) : null;
        if (input && !input.checked) label.click();
        const swatches = [...(row?.querySelectorAll('button,[role="button"],[data-role="button"],[data-name]') || [])]
          .map((item) => ({
            label: item.getAttribute('aria-label') || item.getAttribute('title') || item.getAttribute('data-name') || '',
            background: getComputedStyle(item).backgroundColor,
            color: getComputedStyle(item).color
          })).slice(0, 8);
        return { name, status: input ? 'found' : 'checkbox_not_found', before, after: input ? Boolean(input.checked) : null, swatches };
      });
    })()`,
    returnByValue: true
  });
  const controls = normalized.result?.value || [];
  actions.push(await clickDialogButton(client, "series-properties-dialog", "Ok"));
  await sleep(1000);
  const passed = controls.every((item) => item.status === "found" && item.after === true);
  return { action: "normalize_candle_visibility", status: passed ? "passed" : "needs_review", controls, actions };
}

async function ensureAutomationLayout(client, layoutName) {
  const desired = String(layoutName || "AI OS Automation").trim();
  const active = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const button = [...document.querySelectorAll('button,[role="button"]')].find((item) =>
        /active layout:/i.test(item.getAttribute('aria-label') || '')
      );
      return button?.getAttribute('aria-label') || '';
    })()`,
    returnByValue: true
  });
  if (String(active.result?.value || "").toLowerCase().includes(desired.toLowerCase())) {
    return `automation_layout_already_active:${slug(desired)}`;
  }

  let dialog = await client.call("Runtime.evaluate", {
    expression: `Boolean([...document.querySelectorAll('input')].find((item) => item.placeholder === 'My layout' && item.getBoundingClientRect().width > 0))`,
    returnByValue: true
  });
  if (!dialog.result?.value) {
    const menuResult = await clickNamedControl(client, "Manage layouts");
    await sleep(600);
    const createResult = await clickNamedControl(client, "Create new layout");
    await sleep(700);
    dialog = await client.call("Runtime.evaluate", {
      expression: `Boolean([...document.querySelectorAll('input')].find((item) => item.placeholder === 'My layout' && item.getBoundingClientRect().width > 0))`,
      returnByValue: true
    });
    if (!dialog.result?.value) {
      return `automation_layout_dialog_failed:${menuResult}:${createResult}`;
    }
  }

  const filled = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const input = [...document.querySelectorAll('input')].find((item) => item.placeholder === 'My layout' && item.getBoundingClientRect().width > 0);
      if (!input) return false;
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
      setter?.call(input, ${JSON.stringify(desired)});
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.focus();
      return input.value;
    })()`,
    returnByValue: true
  });
  if (filled.result?.value !== desired) {
    return `automation_layout_name_failed:${slug(String(filled.result?.value || "empty"))}`;
  }
  const created = await clickNamedControl(client, "Create");
  await sleep(2500);
  const current = await client.call("Runtime.evaluate", {
    expression: `(() => [...document.querySelectorAll('button,[role="button"]')].find((item) => /active layout:/i.test(item.getAttribute('aria-label') || ''))?.getAttribute('aria-label') || '')()`,
    returnByValue: true
  });
  return String(current.result?.value || "").toLowerCase().includes(desired.toLowerCase())
    ? `automation_layout_created:${slug(desired)}`
    : `automation_layout_create_unconfirmed:${created}`;
}

async function openIndicatorsDialog(client) {
  await client.call("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "/",
    code: "Slash",
    windowsVirtualKeyCode: 191
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "char",
    text: "/",
    unmodifiedText: "/",
    key: "/",
    code: "Slash",
    windowsVirtualKeyCode: 191
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "/",
    code: "Slash",
    windowsVirtualKeyCode: 191
  });
  await sleep(900);
  const state = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const input = [...document.querySelectorAll('input')].find((item) => {
        const rect = item.getBoundingClientRect();
        const label = [item.placeholder, item.getAttribute('aria-label'), item.getAttribute('data-role')]
          .filter(Boolean).join(' ').toLowerCase();
        return rect.width > 0 && rect.height > 0 && label.includes('search');
      });
      return input ? { placeholder: input.placeholder || '', ariaLabel: input.getAttribute('aria-label') || '' } : null;
    })()`,
    returnByValue: true
  });
  return state.result?.value ? "indicator_dialog_opened:slash" : "indicator_dialog_not_open:slash";
}

async function pressEscape(client) {
  await client.call("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Escape",
    code: "Escape",
    windowsVirtualKeyCode: 27
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Escape",
    code: "Escape",
    windowsVirtualKeyCode: 27
  });
}

async function pressKey(client, key, code, windowsVirtualKeyCode) {
  await client.call("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode });
  await client.call("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode });
}

async function searchIndicatorDialog(client, requestedStudy) {
  const query = String(requestedStudy || "").trim();
  if (!query) return { status: "study_not_requested", query };
  const focused = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const query = ${JSON.stringify(query)};
      const input = [...document.querySelectorAll('input,[role="searchbox"]')].find((item) => {
        const rect = item.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && (item.placeholder || '').toLowerCase().includes('search');
      });
      if (!input) return false;
      input.focus();
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
      if (setter) setter.call(input, '');
      else input.value = '';
      input.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, inputType: 'deleteContentBackward', data: null }));
      input.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
      return true;
    })()`,
    returnByValue: true
  });
  if (!focused.result?.value) return { status: "indicator_search_not_found", query };
  for (const character of query) {
    const codePoint = character.toUpperCase().charCodeAt(0);
    await client.call("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: character,
      windowsVirtualKeyCode: codePoint
    });
    await client.call("Input.dispatchKeyEvent", {
      type: "char",
      key: character,
      text: character,
      unmodifiedText: character,
      windowsVirtualKeyCode: codePoint
    });
    await client.call("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: character,
      windowsVirtualKeyCode: codePoint
    });
  }
  await sleep(1100);
  const candidates = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const dialog = [...document.querySelectorAll('[role="dialog"]')].find((item) => {
        const rect = item.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      });
      if (!dialog) return [];
      return [...dialog.querySelectorAll('*')]
        .map((item) => {
          const rect = item.getBoundingClientRect();
          const directText = [...item.childNodes]
            .filter((node) => node.nodeType === Node.TEXT_NODE)
            .map((node) => node.textContent || '')
            .join(' ')
            .replace(/\\s+/g, ' ')
            .trim();
          return {
            tag: item.tagName.toLowerCase(),
            text: directText.slice(0, 260),
            aria: item.getAttribute('aria-label') || '',
            role: item.getAttribute('role') || '',
            dataName: item.getAttribute('data-name') || '',
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            visible: rect.width > 0 && rect.height > 0
          };
        })
        .filter((item) => item.visible && item.height <= 120 && item.width <= 780 && (item.text || item.aria))
        .slice(0, 80);
    })()`,
    returnByValue: true
  });
  await client.call("Accessibility.enable");
  const accessibilityTree = await client.call("Accessibility.getFullAXTree", { depth: 18 });
  const loweredQuery = query.toLowerCase();
  const axNodes = accessibilityTree.nodes || [];
  const axNodeMap = new Map(axNodes.map((node) => [node.nodeId, node]));
  const accessibleCandidates = axNodes
    .map((node) => ({
      nodeId: node.nodeId,
      parentId: node.parentId,
      backendDOMNodeId: node.backendDOMNodeId,
      role: node.role?.value || "",
      name: node.name?.value || "",
      ignored: Boolean(node.ignored),
      ancestors: (() => {
        const values = [];
        let parent = axNodeMap.get(node.parentId);
        while (parent && values.length < 6) {
          values.push({
            nodeId: parent.nodeId,
            backendDOMNodeId: parent.backendDOMNodeId,
            role: parent.role?.value || "",
            name: parent.name?.value || ""
          });
          parent = axNodeMap.get(parent.parentId);
        }
        return values;
      })()
    }))
    .filter((node) => !node.ignored && node.name && node.name.toLowerCase().includes(loweredQuery))
    .slice(0, 40);
  return {
    status: "indicator_search_complete",
    query,
    candidates: candidates.result?.value || [],
    accessibleCandidates
  };
}

function normalizeStudyRequests(input) {
  if (!Array.isArray(input)) return [];
  return input
    .map((item) => {
      if (typeof item === "string") {
        return { name: item.trim(), search: item.trim(), legend: item.trim() };
      }
      if (!item || typeof item !== "object") return null;
      const name = String(item.name || item.study || item.search || "").trim();
      return name
        ? {
            name,
            search: String(item.search || name).trim(),
            legend: String(item.legend || item.expected_legend || name).trim()
          }
        : null;
    })
    .filter(Boolean);
}

async function clickBackendNode(client, backendDOMNodeId) {
  if (!backendDOMNodeId) return false;
  await client.call("DOM.enable");
  const model = await client.call("DOM.getBoxModel", { backendNodeId: backendDOMNodeId });
  const quad = model.model?.content || model.model?.border;
  if (!Array.isArray(quad) || quad.length < 8) return false;
  const x = (quad[0] + quad[2] + quad[4] + quad[6]) / 4;
  const y = (quad[1] + quad[3] + quad[5] + quad[7]) / 4;
  await clickPoint(client, { x, y });
  return true;
}

async function applyIndicatorStudy(client, request) {
  await pressEscape(client);
  await sleep(250);
  const existing = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const expected = ${JSON.stringify(request.legend.toLowerCase())};
      return (document.body?.innerText || '').toLowerCase().includes(expected);
    })()`,
    returnByValue: true
  });
  if (existing.result?.value) {
    return {
      status: "applied",
      study: request.name,
      search: request.search,
      expected_legend: request.legend,
      legend_verified: true,
      insert_confirmation_verified: false,
      verification_method: "already_present_idempotency_guard"
    };
  }
  const dialogState = await openIndicatorsDialog(client);
  if (!dialogState.startsWith("indicator_dialog_opened")) {
    return { status: "failed", study: request.name, reason: dialogState };
  }
  const searchResult = await searchIndicatorDialog(client, request.search);
  const desired = request.search.toLowerCase();
  const matches = searchResult.accessibleCandidates || [];
  const candidate = matches.find((item) => item.name.toLowerCase() === desired && item.backendDOMNodeId)
    || matches.find((item) => item.name.toLowerCase().startsWith(desired) && item.backendDOMNodeId)
    || matches.find((item) => item.backendDOMNodeId);
  if (!candidate) {
    await pressEscape(client);
    return {
      status: "failed",
      study: request.name,
      search: request.search,
      reason: "accessible_indicator_result_not_found",
      candidates: matches.map((item) => item.name).slice(0, 12)
    };
  }
  const clickedCandidate = await clickBackendNode(client, candidate.backendDOMNodeId);
  if (!clickedCandidate) {
    await pressKey(client, "ArrowDown", "ArrowDown", 40);
    await sleep(180);
    await pressKey(client, "Enter", "Enter", 13);
  }
  await sleep(1300);
  await pressEscape(client);
  await sleep(500);
  const verification = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const expected = ${JSON.stringify(request.legend.toLowerCase())};
      const bodyText = (document.body?.innerText || '').toLowerCase();
      return { matched: bodyText.includes(expected), expected, preview: bodyText.slice(0, 1600) };
    })()`,
    returnByValue: true
  });
  const postActionTree = await client.call("Accessibility.getFullAXTree", { depth: 14 });
  const selectedName = candidate.name.toLowerCase();
  const undoConfirmation = (postActionTree.nodes || []).some((node) => {
    const name = String(node.name?.value || "").toLowerCase();
    return name.includes("undo insert") && name.includes(selectedName);
  });
  const legendVerified = Boolean(verification.result?.value?.matched);
  const verified = legendVerified || undoConfirmation;
  return {
    status: verified ? "applied" : "needs_review",
    study: request.name,
    search: request.search,
    selected_result: candidate.name,
    expected_legend: request.legend,
    legend_verified: legendVerified,
    insert_confirmation_verified: undoConfirmation,
    verification_method: undoConfirmation ? "tradingview_undo_insert_action" : legendVerified ? "dom_legend_text" : "none"
  };
}

async function applyIndicatorStudies(client, requestedStudies) {
  const studies = normalizeStudyRequests(requestedStudies);
  const results = [];
  for (const study of studies) {
    results.push(await applyIndicatorStudy(client, study));
  }
  return results;
}

async function setChartStyle(client, requestedStyle) {
  const desired = String(requestedStyle || "").trim();
  if (!desired) {
    return "chart_style_not_requested";
  }
  await client.call("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    key: "Escape",
    code: "Escape",
    windowsVirtualKeyCode: 27
  });
  await client.call("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "Escape",
    code: "Escape",
    windowsVirtualKeyCode: 27
  });
  await sleep(300);
  const styleButton = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const knownStyles = new Set(['bars', 'candles', 'hollow candles', 'columns', 'line', 'line with markers', 'step line', 'area', 'hlc area', 'baseline', 'high-low', 'heikin ashi', 'renko', 'line break', 'kagi', 'point & figure', 'range']);
      const node = [...document.querySelectorAll('button,[role="button"]')].find((item) => {
        const label = (item.getAttribute('aria-label') || item.getAttribute('title') || '').trim().toLowerCase();
        const rect = item.getBoundingClientRect();
        const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        return knownStyles.has(label) && rect.width > 0 && rect.height > 0 && top && item.contains(top);
      });
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, label: node.getAttribute('aria-label') || node.getAttribute('title') || '' };
    })()`,
    returnByValue: true
  });
  const button = styleButton.result?.value;
  if (!button) {
    return "chart_style_control_not_found";
  }
  if (String(button.label).trim().toLowerCase() === desired.toLowerCase()) {
    return `chart_style_already_${slug(desired)}`;
  }
  await clickPoint(client, button);
  await sleep(700);
  const menuItem = await client.call("Runtime.evaluate", {
    expression: `(() => {
      const desired = ${JSON.stringify(desired.toLowerCase())};
      const nodes = [...document.querySelectorAll('[role="menuitem"],[role="option"],button,div')];
      const node = nodes.find((item) => {
        const label = (item.getAttribute('aria-label') || item.getAttribute('title') || item.textContent || '').trim().toLowerCase();
        const rect = item.getBoundingClientRect();
        const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        return label === desired && rect.width > 0 && rect.height > 0 && rect.width < 700 && rect.height < 100 && top && item.contains(top);
      });
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, label: (node.getAttribute('aria-label') || node.textContent || '').trim() };
    })()`,
    returnByValue: true
  });
  const item = menuItem.result?.value;
  if (!item) {
    return `chart_style_option_not_found:${slug(desired)}`;
  }
  await clickPoint(client, item);
  await sleep(1400);
  return `chart_style_set:${slug(desired)}`;
}

async function main() {
  const payload = parseArgs();
  if (payload.analyze_file || payload.analyzeFile) {
    console.log(JSON.stringify(analyzePngFile(payload.analyze_file || payload.analyzeFile), null, 2));
    return;
  }
  if (payload.action === "option_straddle_layout_request") {
    console.log(JSON.stringify(runFourPaneEvidenceBoard(payload), null, 2));
    return;
  }
  const port = Number(payload.port || 9222);
  const waitMs = Number(payload.wait_ms || payload.waitMs || 9000);
  const captureScreenshot = payload.capture_screenshot !== false && payload.captureScreenshot !== false;
  const qualityCheckEnabled = payload.quality_check !== false && payload.qualityCheck !== false;
  const maxQualityAttempts = Math.max(1, Number(payload.max_quality_attempts || payload.maxQualityAttempts || 3));
  const targetUrl = payload.target_url || payload.targetUrl || buildTradingViewUrl(payload);
  const skipNavigation = payload.skip_navigation === true || payload.skipNavigation === true;
  const includeControls = payload.include_controls === true || payload.includeControls === true;
  const seriesContextOnly = payload.series_context_only === true || payload.seriesContextOnly === true;
  const domTextQuery = String(payload.dom_text_query || payload.domTextQuery || "").trim();
  const artifactRoot = path.resolve(
    payload.artifact_root || payload.artifactRoot || process.env.AI_OS_ARTIFACT_ROOT || defaultArtifactRoot
  );
  const startedAt = new Date().toISOString();
  const nativeActivation = activateTradingViewDesktop(payload.activate_app !== false && payload.activateApp !== false);
  await sleep(nativeActivation === "native_activation_succeeded" ? 1200 : 0);
  const target = await chooseTradingViewTarget(port, payload.target_id || payload.targetId || null);
  const client = new CdpClient(target.webSocketDebuggerUrl);
  await client.connect();

  let screenshotPath = null;
  let screenshotBytes = 0;
  let pageContext = {};
  let quality = null;
  let attempts = 0;
  const recoveryActions = [];
  const setupActions = [];
  let postNavigationActivation = null;
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    try {
      await client.call("Emulation.setFocusEmulationEnabled", { enabled: true });
      recoveryActions.push("focus_emulation_enabled");
    } catch (error) {
      recoveryActions.push(`focus_emulation_unavailable:${error?.name || "error"}`);
    }
    await client.call("Page.bringToFront");
    if (payload.ensure_automation_layout === true || payload.ensureAutomationLayout === true) {
      setupActions.push(await ensureAutomationLayout(client, payload.automation_layout_name || payload.automationLayoutName));
    }
    if (!skipNavigation) {
      await client.call("Page.navigate", { url: targetUrl });
      await sleep(800);
      postNavigationActivation = activateTradingViewDesktop(payload.activate_app !== false && payload.activateApp !== false);
      await sleep(postNavigationActivation === "native_activation_succeeded" ? 1400 : 0);
    }
    const initialSeriesState = await readSeriesState(client);
    if (initialSeriesState.missing_ohlc) {
      setupActions.push(await enableAutoScale(client));
      await sleep(1800);
    }
    if (payload.inspect_control || payload.inspectControl) {
      const requestedControl = payload.inspect_control || payload.inspectControl;
      if (String(requestedControl).toLowerCase().includes("indicator")) {
        setupActions.push(await openIndicatorsDialog(client));
      } else {
        setupActions.push(await clickNamedControl(client, requestedControl));
      }
      await sleep(1200);
    }
    if (payload.close_dialog || payload.closeDialog) {
      setupActions.push(await closeDialogByName(client, payload.close_dialog || payload.closeDialog));
    }
    if (payload.settings_tab || payload.settingsTab) {
      setupActions.push(await clickDialogTab(client, "series-properties-dialog", payload.settings_tab || payload.settingsTab));
    }
    if (payload.normalize_candle_visibility === true || payload.normalizeCandleVisibility === true) {
      setupActions.push(await normalizeCandleVisibility(client));
    }
    if (payload.hover_series_row === true || payload.hoverSeriesRow === true) {
      setupActions.push(await hoverMainSeriesRow(client));
    }
    if (payload.inspect_chart_context_menu === true || payload.inspectChartContextMenu === true) {
      setupActions.push(await openChartContextMenu(client));
    }
    if (payload.indicator_query || payload.indicatorQuery) {
      setupActions.push(await searchIndicatorDialog(client, payload.indicator_query || payload.indicatorQuery));
    }
    const requestedStudies = payload.studies || payload.indicator_studies || payload.indicatorStudies;
    if (Array.isArray(requestedStudies) && requestedStudies.length) {
      if (!skipNavigation) await sleep(3500);
      const studyResults = await applyIndicatorStudies(client, requestedStudies);
      setupActions.push({ action: "apply_indicator_studies", results: studyResults });
    }
    for (let attempt = 1; attempt <= (captureScreenshot ? maxQualityAttempts : 1); attempt += 1) {
      attempts = attempt;
      await sleep(waitMs + (attempt - 1) * 4000);
      if (attempt === 1 && (payload.chart_style || payload.chartStyle)) {
        setupActions.push(await setChartStyle(client, payload.chart_style || payload.chartStyle));
      }
      pageContext = await client.call("Runtime.evaluate", {
        expression: `(() => ({
          title: document.title,
          url: location.href,
          text: (document.body && document.body.innerText || '').slice(0, 1200),
          visible_dialogs: [...document.querySelectorAll('[role="dialog"]')]
            .map((item) => {
              const rect = item.getBoundingClientRect();
              return {
                data_name: item.getAttribute('data-name') || '',
                text: (item.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120),
                visible: rect.width > 0 && rect.height > 0
              };
            }).filter((item) => item.visible),
          controls: ${includeControls && !seriesContextOnly ? `[...document.querySelectorAll('button,[role="button"]')]
            .map((item) => {
              const rect = item.getBoundingClientRect();
              return {
                label: item.getAttribute('aria-label') || item.getAttribute('title') || '',
                data_name: item.getAttribute('data-name') || '',
                pressed: item.getAttribute('aria-pressed'),
                visible: rect.width > 0 && rect.height > 0
              };
            })
            .filter((item) => item.visible && (item.label || item.data_name))
            .slice(0, 160)` : "[]"}
          ,form_controls: ${includeControls && !seriesContextOnly ? `[...document.querySelectorAll('input,[role="searchbox"],[role="option"],[role="dialog"]')]
            .map((item) => {
              const rect = item.getBoundingClientRect();
              return {
                tag: item.tagName.toLowerCase(),
                role: item.getAttribute('role') || '',
                label: item.getAttribute('aria-label') || item.getAttribute('title') || '',
                placeholder: item.getAttribute('placeholder') || '',
                value: item.value || '',
                text: (item.textContent || '').trim().slice(0, 240),
                visible: rect.width > 0 && rect.height > 0,
                width: Math.round(rect.width),
                height: Math.round(rect.height)
              };
            })
            .filter((item) => item.visible)
            .slice(0, 160)` : "[]"}
          ,series_context: ${includeControls ? `[...document.querySelectorAll('*')]
            .filter((item) => /title-/.test(String(item.className || '')) && /main-/.test(String(item.className || '')) && /(?:NSE|BSE|NASDAQ|NYSE)/i.test((item.innerText || '').trim()))
            .slice(0, 12)
            .map((item) => ({
              tag: item.tagName.toLowerCase(),
              class_name: String(item.className || '').slice(0, 240),
              text: (item.innerText || item.textContent || '').trim().slice(0, 240),
              title: item.getAttribute('title') || '',
              aria_label: item.getAttribute('aria-label') || '',
              descendant_controls: [...item.querySelectorAll('button,[role="button"]')].map((control) => ({
                label: control.getAttribute('aria-label') || control.getAttribute('title') || (control.textContent || '').trim(),
                data_name: control.getAttribute('data-name') || '',
                pressed: control.getAttribute('aria-pressed')
              })).slice(0, 20),
              ancestor_controls: (() => {
                let parent = item.parentElement;
                const levels = [];
                for (let depth = 0; parent && depth < 5; depth += 1, parent = parent.parentElement) {
                  levels.push({
                    depth: depth + 1,
                    class_name: String(parent.className || '').slice(0, 180),
                    html: depth <= 2 ? String(parent.outerHTML || '').slice(0, 2400) : '',
                    controls: [...parent.querySelectorAll('button,[role="button"]')].map((control) => ({
                      label: control.getAttribute('aria-label') || control.getAttribute('title') || (control.textContent || '').trim(),
                      data_name: control.getAttribute('data-name') || '',
                      pressed: control.getAttribute('aria-pressed')
                    })).slice(0, 20)
                  });
                }
                return levels;
              })()
            }))` : "[]"}
          ,dom_text_matches: ${domTextQuery ? `[...document.querySelectorAll('*')]
            .map((item) => {
              const rect = item.getBoundingClientRect();
              const text = (item.innerText || item.textContent || '').trim();
              const top = rect.width > 0 && rect.height > 0 ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) : null;
              return {
                tag: item.tagName.toLowerCase(),
                text: text.slice(0, 180),
                class_name: String(item.className || '').slice(0, 220),
                role: item.getAttribute('role') || '',
                data_name: item.getAttribute('data-name') || '',
                data_value: item.getAttribute('data-value') || '',
                title: item.getAttribute('title') || '',
                visible: rect.width > 0 && rect.height > 0,
                topmost: Boolean(top && item.contains(top)),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
              };
            })
            .filter((item) => item.visible && item.text.toLowerCase().includes(${JSON.stringify(domTextQuery.toLowerCase())}))
            .sort((left, right) => left.text.length - right.text.length || left.width * left.height - right.width * right.height)
            .slice(0, 60)` : "[]"}
        }))()`,
        returnByValue: true
      });
      if (!captureScreenshot) {
        break;
      }
      const screenshot = await client.call("Page.captureScreenshot", { format: "png", fromSurface: true });
      let screenshotBuffer = Buffer.from(screenshot.data || "", "base64");
      quality = qualityCheckEnabled
        ? { ...analyzeScreenshotQuality(screenshotBuffer), attempt, capture_surface: "compositor" }
        : { status: "skipped", reason: "quality_check_disabled", attempt };
      if (qualityCheckEnabled && quality.status !== "passed") {
        const alternate = await client.call("Page.captureScreenshot", { format: "png", fromSurface: false });
        const alternateBuffer = Buffer.from(alternate.data || "", "base64");
        const alternateQuality = {
          ...analyzeScreenshotQuality(alternateBuffer),
          attempt,
          capture_surface: "view"
        };
        const qualitySignal = (candidate) => Number(candidate.chart_like_ratio || 0) + Number(candidate.saturated_ratio || 0);
        if (alternateQuality.status === "passed" || qualitySignal(alternateQuality) > qualitySignal(quality)) {
          screenshotBuffer = alternateBuffer;
          quality = alternateQuality;
          recoveryActions.push("alternate_view_surface_capture_selected");
        }
      }
      const visibleDialogs = pageContext.result?.value?.visible_dialogs || [];
      if (qualityCheckEnabled && visibleDialogs.length) {
        quality = {
          ...quality,
          status: "failed",
          reason: "modal_overlay_visible",
          visible_dialogs: visibleDialogs,
          attempt
        };
      }
      const dateFolder = new Date().toISOString().slice(0, 10).replaceAll("-", "");
      const artifactDir = path.join(artifactRoot, "tradingview", dateFolder);
      fs.mkdirSync(artifactDir, { recursive: true });
      const symbols = normalizeSymbols(payload.symbols);
      const qualitySuffix = quality.status === "passed" ? "" : `-${quality.status}`;
      const fileName = `${new Date().toISOString().replace(/[:.]/g, "-")}-${slug(symbols[0] || payload.symbol || "chart")}${qualitySuffix}.png`;
      screenshotPath = path.join(artifactDir, fileName);
      fs.writeFileSync(screenshotPath, screenshotBuffer);
      screenshotBytes = fs.statSync(screenshotPath).size;
      if (quality.status === "passed" || !qualityCheckEnabled) {
        break;
      }
      await client.call("Page.bringToFront");
      if (attempt === 1) {
        recoveryActions.push(await resetChartFromMenu(client));
      } else if (attempt === 2) {
        recoveryActions.push(await enableAutoScale(client));
      }
      await client.call("Runtime.evaluate", { expression: "window.dispatchEvent(new Event('resize')); true", returnByValue: true });
    }
  } finally {
    client.close();
  }

  const value = pageContext.result?.value || {};
  const studyAction = setupActions.find((item) => item && typeof item === "object" && item.action === "apply_indicator_studies");
  const studyResults = studyAction?.results || [];
  const studyApplicationStatus = !studyResults.length
    ? "not_requested"
    : studyResults.every((item) => item.status === "applied")
      ? "passed"
      : "failed";
  const qualityStatus = quality?.status || "not_checked";
  const result = {
    status: qualityStatus === "failed" || studyApplicationStatus === "failed" ? "needs_review" : "done",
    action: payload.action || "open_chart_capture",
    action_dispatch_status: ["open_chart_capture", "formula_chart_request", "indicator_layout_request", "fundamental_chart_request"].includes(payload.action || "open_chart_capture") ? "passed" : "generic_capture_only",
    target_url: targetUrl,
    page_url: value.url || targetUrl,
    page_title: value.title || null,
    extracted_text_preview: value.text || "",
    chart_controls: value.controls || [],
    form_controls: value.form_controls || [],
    series_context: value.series_context || [],
    dom_text_matches: value.dom_text_matches || [],
    visible_dialogs: value.visible_dialogs || [],
    screenshot_path: screenshotPath,
    screenshot_bytes: screenshotBytes,
    artifact_quality_status: qualityStatus,
    artifact_quality: quality,
    quality_attempts: attempts,
    chart_setup_actions: setupActions,
    study_results: studyResults,
    study_application_status: studyApplicationStatus,
    quality_recovery_actions: recoveryActions,
    cdp_target_id: target.id,
    cdp_target_title: target.title,
    started_at: startedAt,
    finished_at: new Date().toISOString(),
    symbols: normalizeSymbols(payload.symbols),
    exchange: payload.exchange || null,
    timeframe: payload.timeframe || null,
    chart_layout: payload.chart_layout || payload.chartLayout || null,
    chart_style: payload.chart_style || payload.chartStyle || null,
    native_activation: nativeActivation,
    post_navigation_activation: postNavigationActivation
  };
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({ status: "failed", error: error.name, message: error.message }, null, 2));
  process.exit(1);
});
