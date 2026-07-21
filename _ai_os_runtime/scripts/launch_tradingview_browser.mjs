#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";

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
const systemChromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const configuredExecutablePath = process.env.AI_OS_TRADINGVIEW_BROWSER_EXECUTABLE;
const executablePath = [configuredExecutablePath, systemChromePath]
  .filter(Boolean)
  .find((candidate) => fs.existsSync(candidate));

if (!executablePath) {
  throw new Error("No supported Chromium executable is available");
}

fs.mkdirSync(profileDir, { recursive: true });

let closing = false;
const browserProcess = spawn(executablePath, [
  "--remote-debugging-address=127.0.0.1",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profileDir}`,
  "--no-first-run",
  "--no-default-browser-check",
  "--password-store=basic",
  "--use-mock-keychain",
  "--disable-sync",
  initialUrl
], { stdio: ["ignore", "inherit", "inherit"] });

browserProcess.once("exit", (code, signal) => {
  if (closing) return;
  console.error(JSON.stringify({ status: "browser_exited", code, signal }));
  process.exit(code ?? 1);
});

async function waitForCdp() {
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`, {
        signal: AbortSignal.timeout(3000)
      });
      if (response.ok) return response.json();
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Chrome CDP did not become ready on port ${port}`);
}

const cdpVersion = await waitForCdp();

console.log(JSON.stringify({
  status: "ready",
  backend: executablePath === systemChromePath ? "system_chrome" : "chrome_for_testing",
  port,
  profile_dir: profileDir,
  executable_path: executablePath,
  page_url: initialUrl,
  cdp_browser: cdpVersion.Browser,
  pid: process.pid
}));

async function shutdown(signal) {
  if (closing) return;
  closing = true;
  console.log(JSON.stringify({ status: "stopping", signal }));
  browserProcess.kill("SIGTERM");
  process.exit(0);
}

process.on("SIGINT", () => void shutdown("SIGINT"));
process.on("SIGTERM", () => void shutdown("SIGTERM"));
await new Promise(() => {});
