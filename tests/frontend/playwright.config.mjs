// Playwright config for the frontend tests. The repo has no package.json and
// no local node_modules by design: the runner resolves @playwright/test via a
// junction at node_modules/@playwright/test -> the globally installed package
// (dev-only, gitignored). The webServer is Python's stdlib http.server serving
// the repo root, so the app's absolute /static/* URLs resolve unchanged.
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

export default {
  testDir: ".",
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8123",
    headless: true,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: "python -m http.server 8123 --bind 127.0.0.1",
    cwd: root,
    url: "http://127.0.0.1:8123/static/index.html",
    reuseExistingServer: true,
    timeout: 20000,
  },
};