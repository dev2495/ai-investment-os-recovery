import { defineConfig } from "@playwright/test";

export default defineConfig({
  expect: { timeout: 10_000 },
  fullyParallel: true,
  outputDir: "/tmp/ai-os-playwright-results",
  reporter: [["list"]],
  testDir: "./tests",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:5177",
    browserName: "chromium",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  workers: 4
});
