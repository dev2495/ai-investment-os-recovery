#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const runtimeRoot = path.resolve(scriptDir, "..");
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(runtimeRoot, "ai-office-ui", "node_modules", "playwright"));

function readArg(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const port = Number(readArg("port", process.env.AI_OS_TRADINGVIEW_BROWSER_PORT || "9333"));
const profileDir = path.resolve(readArg(
  "profile-dir",
  process.env.AI_OS_TRADINGVIEW_BROWSER_PROFILE || "/Volumes/Devarsh SSD/AI OS Data/browser-profiles/tradingview-cft"
));
const initialUrl = readArg(
  "url",
  process.env.AI_OS_TRADINGVIEW_INITIAL_URL || "https://www.tradingview.com/chart/?symbol=NASDAQ%3AAAPL"
);
const executablePath = chromium.executablePath();

fs.mkdirSync(profileDir, { recursive: true });

const context = await chromium.launchPersistentContext(profileDir, {
  executablePath,
  headless: false,
  viewport: null,
  args: [
    `--remote-debugging-port=${port}`,
    "--no-first-run",
    "--no-default-browser-check"
  ]
});

let page = context.pages().find((candidate) => candidate.url().startsWith("https://www.tradingview.com"));
if (!page) {
  page = context.pages()[0] || await context.newPage();
}
if (!page.url().startsWith("https://www.tradingview.com/chart")) {
  await page.goto(initialUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
}

console.log(JSON.stringify({
  status: "ready",
  backend: "chrome_for_testing",
  port,
  profile_dir: profileDir,
  executable_path: executablePath,
  page_url: page.url(),
  pid: process.pid
}));

let closing = false;
async function shutdown(signal) {
  if (closing) return;
  closing = true;
  console.log(JSON.stringify({ status: "stopping", signal }));
  await context.close().catch(() => {});
  process.exit(0);
}

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));
await new Promise(() => {});
