import fs from "node:fs";
import path from "node:path";
import { defineConfig, chromium } from "@playwright/test";

const defaultExe = chromium.executablePath();
const fallbackExe = "/home/kanish/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome";
const executablePath = fs.existsSync(defaultExe) ? defaultExe : fallbackExe;

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.mjs/,
  timeout: 65_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3100",
    headless: true,
    launchOptions: {
      executablePath,
    },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start -- -p 3100 -H 127.0.0.1",
    port: 3100,
    reuseExistingServer: false,
    timeout: 60_000,
    cwd: path.resolve("."),
  },
});
