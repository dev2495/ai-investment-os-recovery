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

async function chooseTradingViewTarget(port) {
  const targets = await fetchJson(`http://127.0.0.1:${port}/json/list`);
  const pages = targets.filter((target) => target.type === "page" && target.webSocketDebuggerUrl);
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
      const nodes = [...document.querySelectorAll('button,[role="button"]')];
      const node = nodes.find((item) => {
        const label = [item.getAttribute('aria-label'), item.getAttribute('title'), item.textContent]
          .filter(Boolean).join(' ').toLowerCase();
        const rect = item.getBoundingClientRect();
        const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        return label.includes('auto scale') && rect.width > 0 && rect.height > 0 && top && item.contains(top);
      });
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
      const nodes = [...document.querySelectorAll('button,[role="button"]')];
      const node = nodes.find((item) => {
        const label = [item.getAttribute('aria-label'), item.getAttribute('title'), item.getAttribute('data-name'), item.textContent]
          .filter(Boolean).join(' ').trim().toLowerCase();
        const rect = item.getBoundingClientRect();
        const top = rect.width > 0 && rect.height > 0
          ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
          : null;
        return (label === desired || label.includes(desired)) && rect.width > 0 && rect.height > 0 && top && item.contains(top);
      });
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
  await pressKey(client, "ArrowDown", "ArrowDown", 40);
  await sleep(180);
  await pressKey(client, "Enter", "Enter", 13);
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
  const port = Number(payload.port || 9222);
  const waitMs = Number(payload.wait_ms || payload.waitMs || 9000);
  const captureScreenshot = payload.capture_screenshot !== false && payload.captureScreenshot !== false;
  const qualityCheckEnabled = payload.quality_check !== false && payload.qualityCheck !== false;
  const maxQualityAttempts = Math.max(1, Number(payload.max_quality_attempts || payload.maxQualityAttempts || 3));
  const targetUrl = payload.target_url || payload.targetUrl || buildTradingViewUrl(payload);
  const skipNavigation = payload.skip_navigation === true || payload.skipNavigation === true;
  const includeControls = payload.include_controls === true || payload.includeControls === true;
  const artifactRoot = path.resolve(
    payload.artifact_root || payload.artifactRoot || process.env.AI_OS_ARTIFACT_ROOT || defaultArtifactRoot
  );
  const startedAt = new Date().toISOString();
  const nativeActivation = activateTradingViewDesktop(payload.activate_app !== false && payload.activateApp !== false);
  await sleep(nativeActivation === "native_activation_succeeded" ? 1200 : 0);
  const target = await chooseTradingViewTarget(port);
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
    await client.call("Page.bringToFront");
    if (!skipNavigation) {
      await client.call("Page.navigate", { url: targetUrl });
      await sleep(800);
      postNavigationActivation = activateTradingViewDesktop(payload.activate_app !== false && payload.activateApp !== false);
      await sleep(postNavigationActivation === "native_activation_succeeded" ? 1400 : 0);
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
          controls: ${includeControls ? `[...document.querySelectorAll('button,[role="button"]')]
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
          ,form_controls: ${includeControls ? `[...document.querySelectorAll('input,[role="searchbox"],[role="option"],[role="dialog"]')]
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
        }))()`,
        returnByValue: true
      });
      if (!captureScreenshot) {
        break;
      }
      const screenshot = await client.call("Page.captureScreenshot", { format: "png", fromSurface: true });
      const data = screenshot.data || "";
      const screenshotBuffer = Buffer.from(data, "base64");
      quality = qualityCheckEnabled
        ? { ...analyzeScreenshotQuality(screenshotBuffer), attempt }
        : { status: "skipped", reason: "quality_check_disabled", attempt };
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
        recoveryActions.push(await resetChartView(client));
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
  const result = {
    status: "done",
    action: payload.action || "open_chart_capture",
    target_url: targetUrl,
    page_url: value.url || targetUrl,
    page_title: value.title || null,
    extracted_text_preview: value.text || "",
    chart_controls: value.controls || [],
    form_controls: value.form_controls || [],
    screenshot_path: screenshotPath,
    screenshot_bytes: screenshotBytes,
    artifact_quality_status: quality?.status || "not_checked",
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
