// Playwright coverage for the rewritten Bottleneck section: user-authored
// topics rendered from GET /api/bottleneck/topics, with expandable stock thesis
// cards, an unranked anchor strip, ranked underdogs with a market-cap ceiling,
// tri-state checklist flags, the generate→review→apply flow (transport mocked),
// and JSON import/export.
//
// The section renders from the topics endpoint alone — the dashboard payload's
// `bottleneck` key is not a render source, so these tests serve the section
// payload directly.

import { test, expect } from "@playwright/test";
import { mockApi, installMockDashboard, BOTTLENECK_CEILING, bottleneckJob } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";
const AS_OF = "2026-09-25T12:00:00Z";

function stock(overrides = {}) {
  return {
    ticker: "XXXX", name: "", stance: "",
    why_chokepoint: "", layer: "", role: "downstream", tier: "anchor",
    evidence: [], catalyst: "", catalyst_window: "", invalidation: [],
    dilution_atm: null, customer_concentration: null, gaap_margin: null, financing_quality: null,
    metrics: {
      market_cap: null, roc_40d: null, move_1y: null,
      forward_pe: null, revenue_growth: null, as_of: AS_OF,
    },
    provenance: { model: "", skill_snapshot: "", prompt_hash: "", run_ts: "" },
    ...overrides,
  };
}

function rawUpstream() {
  return [
    { name: "Transformers", physical_constraint: "Lead times run past 2027", what_to_watch: "Order backlog and price", stocks: ["ETN", "POWL"] },
    { name: "Switchgear", physical_constraint: "Qualified capacity is thin", what_to_watch: "Book-to-bill", stocks: [] },
  ];
}

function rawDownstream() {
  return {
    anchor: [
      stock({
        ticker: "VRT", name: "Vertiv Holdings", stance: "Own", tier: "anchor",
        layer: "Thermal management",
        why_chokepoint: "Direct liquid cooling is the default for the newest racks.",
        metrics: { market_cap: 30_000_000_000, roc_40d: 8.1, move_1y: 40.2, forward_pe: 24.5, revenue_growth: 0.18, as_of: AS_OF },
        evidence: [{ claim: "Backlog grew 30% year over year", source: "10-Q", source_url: "https://example.com/vrt-10q", tier: "primary-filing" }],
        catalyst: "Q4 orders", catalyst_window: "Q4 2026",
        invalidation: ["Hyperscaler capex cuts"],
        customer_concentration: true,
      }),
      stock({
        ticker: "ETN", name: "Eaton", stance: "Watch", tier: "anchor",
        metrics: { market_cap: 130_000_000_000, roc_40d: 4.4, move_1y: 18.0, forward_pe: 28.0, revenue_growth: 0.09, as_of: AS_OF },
      }),
    ],
    underdogs: [
      stock({
        ticker: "AAOI", name: "Applied Optoelectronics", stance: "Speculative",
        layer: "Optical modules", tier: "underdog",
        why_chokepoint: "US-made optical transceivers are the constrained step.",
        metrics: { market_cap: 8_691_007_488, roc_40d: 22.4, move_1y: null, forward_pe: 22.24, revenue_growth: 0.864, as_of: AS_OF },
        evidence: [
          { claim: "Customer concentration above 50%", source: "10-K", source_url: "https://example.com/aaoi-10k", tier: "primary-filing" },
          { claim: "Analyst raised target", source: "Broker note", source_url: null, tier: "sell-side" },
        ],
        catalyst: "800G ramp", catalyst_window: "1H 2027",
        invalidation: ["Design loss at lead customer"],
        dilution_atm: true, customer_concentration: true, gaap_margin: false, financing_quality: null,
        provenance: { model: "deepseek-v4.1-flash", skill_snapshot: "abcdef0123456789", prompt_hash: "9876543210fedcba", run_ts: AS_OF },
      }),
      stock({
        ticker: "AXTI", name: "AXT", stance: "Speculative",
        layer: "Compound substrates", tier: "underdog",
        why_chokepoint: "Substrate supply is a single qualified source.",
        metrics: { market_cap: 2_100_000_000, roc_40d: -6.5, move_1y: null, forward_pe: -4.2, revenue_growth: null, as_of: AS_OF },
        evidence: [{ claim: "Loss-making on a GAAP basis", source: "8-K", source_url: "https://example.com/axti-8k", tier: "company-release" }],
      }),
      stock({
        ticker: "MYST", name: "Unpriced Co", stance: "",
        layer: "Unknown", tier: "underdog",
        metrics: { market_cap: null, roc_40d: null, move_1y: null, forward_pe: null, revenue_growth: null, as_of: null },
      }),
    ],
  };
}

function sampleTopics() {
  return [
    {
      id: "t1", name: "Grid power for data centers",
      created: AS_OF, updated: AS_OF, underdog_ceiling: BOTTLENECK_CEILING,
      upstream: rawUpstream(), downstream: rawDownstream(), revisions: [],
    },
  ];
}

function samplePayload(generation = { enabled: false, error: null }) {
  return {
    topics: sampleTopics(),
    bottleneck: {
      as_of: AS_OF,
      framework: "serenity-aleabitoreddit",
      thesis: "Trace each demand driver to the scarce physical layer the build cannot bypass.",
      topics: [
        {
          id: "t1", name: "Grid power for data centers",
          created: AS_OF, updated: AS_OF, underdog_ceiling: BOTTLENECK_CEILING,
          upstream: [
            { name: "Transformers", physical_constraint: "Lead times run past 2027", what_to_watch: "Order backlog and price", stocks: ["ETN", "POWL"], roc_40d_pct: 12.3, as_of: AS_OF },
            { name: "Switchgear", physical_constraint: "Qualified capacity is thin", what_to_watch: "Book-to-bill", stocks: [], roc_40d_pct: null, as_of: AS_OF },
          ],
          downstream: rawDownstream(),
          note: "Upstream layers rank by 40-day ROC. Underdogs are capped at $3B and rank by the same measure; momentum is a stress gauge, not a thesis.",
        },
      ],
      strongest_signal: {
        name: "Transformers", physical_constraint: "Lead times run past 2027",
        what_to_watch: "Order backlog and price", stocks: ["ETN", "POWL"],
        roc_40d_pct: 12.3, as_of: AS_OF, topic_id: "t1", topic_name: "Grid power for data centers",
      },
      note: "Each chokepoint still requires primary-source validation before it becomes actionable.",
    },
    generation,
  };
}

// A tiny stateful server so create/apply/import round-trips are observable.
function makeServer(payload) {
  return { payload, calls: { create: [], update: [], delete: [], generate: [], apply: [], import: [] } };
}

async function mockSection(page, server) {
  const p = server.payload;
  await page.route("**/api/bottleneck/topics", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(p) })
  );
  await page.route("**/api/bottleneck/topics/export", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ version: 1, topics: p.topics }) })
  );
  await page.route("**/api/bottleneck/topics/import", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    server.calls.import.push(body);
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ imported: 1, errors: ["topic[bad]: name is required and must be a non-empty string"], topics: p.topics }),
    });
  });
  await page.route("**/api/bottleneck/topics/generate", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    server.calls.generate.push(body);
    const detail = server.generateError;
    if (detail) {
      route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail }) });
      return;
    }
    route.fulfill({
      status: 201, contentType: "application/json",
      body: JSON.stringify(bottleneckJob({ theme: body.theme, topic_id: body.topic_id })),
    });
  });
  await page.route("**/api/bottleneck/jobs/job1", (route) => {
    const job = server.job || {
      id: "job1", status: "succeeded", theme: "Grid power", model: "deepseek-v4.1-flash",
      topic_id: "t1", created: AS_OF, updated: AS_OF, error: null,
      draft: {
        topic: {
          name: "Grid power (draft)", underdog_ceiling: BOTTLENECK_CEILING,
          upstream: [{ name: "Transformers", physical_constraint: "Long lead times", stocks: ["ETN"] }],
          downstream: {
            anchor: [stock({ ticker: "VRT", name: "Vertiv", tier: "anchor" })],
            underdogs: [stock({ ticker: "AAOI", name: "Applied Optoelectronics", tier: "underdog" })],
          },
        },
        provenance: { model: "deepseek-v4.1-flash", skill_snapshot: "abc123def456", prompt_hash: "fff000111222", run_ts: AS_OF },
      },
    };
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(job) });
  });
  await page.route("**/api/bottleneck/jobs/job1/cancel", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "job1", status: "cancelled", draft: null }) })
  );
  await page.route("**/api/bottleneck/jobs/job1/apply", async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    server.calls.apply.push(body);
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(server.payload.topics[0]) });
  });
  await page.route("**/api/bottleneck/topics/*", async (route) => {
    const req = route.request();
    const id = new URL(req.url()).pathname.split("/").pop();
    if (req.method() === "PUT") {
      const patch = JSON.parse(req.postData() || "{}");
      server.calls.update.push({ id, patch });
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id, ...patch }) });
      return;
    }
    if (req.method() === "DELETE") {
      server.calls.delete.push(id);
      p.topics = p.topics.filter((t) => t.id !== id);
      p.bottleneck.topics = p.bottleneck.topics.filter((t) => t.id !== id);
      route.fulfill({ status: 204 });
      return;
    }
    route.fallback();
  });
  await page.route("**/api/bottleneck/topics", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = JSON.parse(route.request().postData() || "{}");
    server.calls.create.push(body);
    const raw = {
      id: "tnew", name: body.name, created: AS_OF, updated: AS_OF, underdog_ceiling: BOTTLENECK_CEILING,
      upstream: [], downstream: { anchor: [], underdogs: [] }, revisions: [],
    };
    p.topics = [...p.topics, raw];
    p.bottleneck.topics = [...p.bottleneck.topics, {
      id: "tnew", name: body.name, created: AS_OF, updated: AS_OF, underdog_ceiling: BOTTLENECK_CEILING,
      upstream: [], downstream: { anchor: [], underdogs: [] }, note: "",
    }];
    route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(raw) });
  });
}

async function boot(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
}

test.describe("Bottleneck topics", () => {
  test("empty state offers create or generate", async ({ page }) => {
    const server = makeServer({ topics: [], bottleneck: { as_of: AS_OF, framework: "serenity-aleabitoreddit", thesis: "t", topics: [], strongest_signal: null, note: "empty" }, generation: { enabled: true, error: null } });
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    await expect(page.locator(".bn-empty")).toBeVisible();
    await expect(page.locator('.bn-empty [data-bn-action="new-topic"]')).toBeVisible();
    await expect(page.locator('.bn-empty [data-bn-action="generate"]')).toBeEnabled();
    await expect(page.locator(".bn-topic")).toHaveCount(0);
  });

  test("create a topic from the front-end", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    await page.locator('[data-bn-action="new-topic"]').first().click();
    const form = page.locator('form[data-bn-form="new-topic"]');
    await expect(form).toBeVisible();
    await form.locator('input[data-field="name"]').fill("Copper for grid buildout");
    await form.locator('button[type="submit"]').click();

    await expect.poll(() => server.calls.create).toEqual([{ name: "Copper for grid buildout" }]);
    // The created topic opens its editor.
    await expect(page.locator(".bn-editor")).toBeVisible();
    await expect(page.locator('.bn-editor input[data-field="name"]')).toHaveValue("Copper for grid buildout");
  });

  test("expanding a topic and a stock card", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    const topic = page.locator('.bn-topic[data-topic-id="t1"]');
    await expect(topic.locator(".bn-topic-body")).toHaveCount(0);
    await topic.locator(".bn-topic-toggle").click();
    await expect(topic.locator(".bn-topic-body")).toBeVisible();
    await expect(topic.locator(".bn-topic-toggle")).toHaveAttribute("aria-expanded", "true");

    // Upstream layers render with their momentum; a null momentum reads "—".
    const layers = topic.locator(".bn-layer");
    await expect(layers).toHaveCount(2);
    await expect(layers.nth(0).locator(".bn-layer-name")).toHaveText("Transformers");
    await expect(layers.nth(0).locator(".bn-layer-roc")).toHaveText("+12.30%");
    await expect(layers.nth(1).locator(".bn-layer-roc")).toHaveText("\u2014");

    // Expand one underdog card.
    const aaoi = topic.locator('.bn-stock[data-stock-key*="AAOI"]');
    await expect(aaoi.locator(".bn-stock-body")).toHaveCount(0);
    await aaoi.locator(".bn-stock-toggle").click();
    await expect(aaoi.locator(".bn-stock-body")).toBeVisible();
    await expect(aaoi.locator(".bn-stock-toggle")).toHaveAttribute("aria-expanded", "true");
  });

  test("anchor strip is unranked; underdogs are ranked under the ceiling", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);
    await page.locator('.bn-topic[data-topic-id="t1"] .bn-topic-toggle').click();

    const topic = page.locator('.bn-topic[data-topic-id="t1"]');
    // Ceiling is printed on the section, not computed here.
    await expect(topic.locator(".bn-band-underdog .bn-subhead-note")).toContainText("below $3B market cap");
    await expect(topic.locator('.bn-chip.ceiling')).toHaveText("\u2264 $3B");

    // Anchors: payload order preserved, no rank numbers.
    const anchors = topic.locator(".bn-strip .bn-stock");
    await expect(anchors).toHaveCount(2);
    await expect(anchors.nth(0).locator(".bn-stock-ticker")).toHaveText("VRT");
    await expect(anchors.nth(1).locator(".bn-stock-ticker")).toHaveText("ETN");
    await expect(topic.locator(".bn-strip .bn-rank")).toHaveCount(0);

    // Underdogs: ranked #1..#3 under the ceiling.
    const dogs = topic.locator(".bn-band-underdog .bn-stock");
    await expect(dogs).toHaveCount(3);
    await expect(dogs.nth(0).locator(".bn-rank")).toHaveText("#1");
    await expect(dogs.nth(2).locator(".bn-rank")).toHaveText("#3");
  });

  test("null renders as an em dash, never as a zero; a negative PE renders signed", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);
    await page.locator('.bn-topic[data-topic-id="t1"] .bn-topic-toggle').click();

    const topic = page.locator('.bn-topic[data-topic-id="t1"]');
    // AAOI: values trace straight to the payload.
    const aaoi = topic.locator('.bn-stock[data-stock-key*="AAOI"]');
    await aaoi.locator(".bn-stock-toggle").click();
    await expect(aaoi.locator(".bn-stock-roc")).toHaveText("+22.40%");
    const aaoiMetrics = aaoi.locator(".bn-metric");
    await expect(aaoiMetrics.filter({ hasText: "Market cap" }).locator(".bn-metric-value")).toHaveText("$8.69B");
    await expect(aaoiMetrics.filter({ hasText: "Forward PE" }).locator(".bn-metric-value")).toHaveText("22.24\u00d7");
    // 1-year move is null in the payload → em dash, not 0.
    await expect(aaoiMetrics.filter({ hasText: "1-year move" }).locator(".bn-metric-value")).toHaveText("\u2014");

    // AXTI: a loss-maker's negative forward PE is real data, shown signed.
    const axti = topic.locator('.bn-stock[data-stock-key*="AXTI"]');
    await axti.locator(".bn-stock-toggle").click();
    await expect(axti.locator(".bn-metric").filter({ hasText: "Forward PE" }).locator(".bn-metric-value")).toHaveText("-4.20\u00d7");
    await expect(axti.locator(".bn-stock-roc")).toHaveText("-6.50%");

    // MYST: every metric null → em dashes; never a zero.
    const myst = topic.locator('.bn-stock[data-stock-key*="MYST"]');
    await myst.locator(".bn-stock-toggle").click();
    const mystValues = await myst.locator(".bn-metric-value").allTextContents();
    expect(mystValues).toEqual(["\u2014", "\u2014", "\u2014", "\u2014", "\u2014"]);
    expect(mystValues.join("")).not.toContain("0");
  });

  test("checklist flags are tri-state and evidence tiers are visible", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);
    await page.locator('.bn-topic[data-topic-id="t1"] .bn-topic-toggle').click();

    const aaoi = page.locator('.bn-topic[data-topic-id="t1"] .bn-stock[data-stock-key*="AAOI"]');
    await aaoi.locator(".bn-stock-toggle").click();

    const flags = aaoi.locator(".bn-flag");
    await expect(flags.filter({ hasText: "Dilution / ATM" })).toHaveClass(/yes/);
    await expect(flags.filter({ hasText: "GAAP margin" })).toHaveClass(/no/);
    // financing_quality is null in the payload → "not assessed", not "no".
    await expect(flags.filter({ hasText: "Financing quality" })).toHaveClass(/na/);
    await expect(flags.filter({ hasText: "Financing quality" })).toContainText("not assessed");

    // Trust tiers: primary filing vs sell-side are distinguishable.
    await expect(aaoi.locator(".bn-ev-tier.t-primary-filing")).toHaveCount(1);
    await expect(aaoi.locator(".bn-ev-tier.t-sell-side")).toHaveCount(1);
    // Agent provenance is reachable on the card.
    await expect(aaoi.locator(".bn-prov")).toContainText("deepseek-v4.1-flash");
  });

  test("generation disabled explains why before a click", async ({ page }) => {
    const server = makeServer(samplePayload({ enabled: false, error: "Topic generation is disabled: no OPENCODE_GO_API_KEY found. Add OPENCODE_GO_API_KEY=<key> to the repo-root .env file and retry." }));
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    const gen = page.locator('.bn-toolbar [data-bn-action="generate"]');
    await expect(gen).toBeDisabled();
    await expect(page.locator(".bn-gen-off")).toContainText("no OPENCODE_GO_API_KEY found");
  });

  test("generate → review → apply never touches the store until applied", async ({ page }) => {
    const server = makeServer(samplePayload({ enabled: true, error: null }));
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    await page.locator('.bn-toolbar [data-bn-action="generate"]').click();
    const genForm = page.locator('form[data-bn-form="generate"]');
    await genForm.locator('input[data-field="theme"]').fill("Grid power");
    await genForm.locator('button[type="submit"]').click();

    // Review panel appears; nothing applied yet.
    const review = page.locator(".bn-job.review");
    await expect(review).toBeVisible();
    await expect(review).toContainText("not applied yet");
    await expect(review).toContainText("Grid power (draft)");
    await expect(review.locator(".bn-prov")).toContainText("deepseek-v4.1-flash");
    expect(server.calls.apply).toHaveLength(0);

    // Apply writes to the preselected target topic.
    await review.locator('[data-bn-action="apply-draft"]').click();
    await expect.poll(() => server.calls.apply).toEqual([{ topic_id: "t1", summary: "Applied agent draft for theme: Grid power" }]);
    await expect(page.locator(".bn-job.review")).toHaveCount(0);
  });

  test("a 409 from generate shows the server's exact message", async ({ page }) => {
    const server = makeServer(samplePayload({ enabled: true, error: null }));
    server.generateError = "another topic generation is already running; wait for it to finish or cancel it first";
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    await page.locator('.bn-toolbar [data-bn-action="generate"]').click();
    const genForm = page.locator('form[data-bn-form="generate"]');
    await genForm.locator('input[data-field="theme"]').fill("Anything");
    await genForm.locator('button[type="submit"]').click();

    await expect(genForm.locator("[data-bn-msg]")).toHaveText("another topic generation is already running; wait for it to finish or cancel it first");
  });

  test("in-flight job is recovered on load", async ({ page }) => {
    const server = makeServer(samplePayload({ enabled: true, error: null }));
    // A legacy persisted job: no `stages`, so the panel keeps the old bar.
    server.job = { id: "job1", status: "running", theme: "Recovered run", model: "deepseek-v4.1-flash", topic_id: null, created: AS_OF, updated: AS_OF, error: null, draft: null };
    await mockApi(page);
    await mockSection(page, server);
    // The jobs list reports the in-flight job so recovery can pick it up.
    await page.route("**/api/bottleneck/jobs", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([server.job]) })
    );
    await boot(page);

    await expect(page.locator(".bn-job")).toContainText("Recovered run");
    await expect(page.locator('.bn-job [data-bn-action="cancel-job"]')).toBeVisible();
    // No stages on a legacy job -> the indeterminate bar stays, and the stage
    // list never renders as an empty box.
    await expect(page.locator(".bn-job .bn-progress")).toBeVisible();
    await expect(page.locator(".bn-job .bn-stages")).toHaveCount(0);

    // Cancelling the recovered run is cooperative and reports cleanly.
    await page.locator('.bn-job [data-bn-action="cancel-job"]').click();
    await expect(page.locator(".bn-job")).toContainText("Generation cancelled");
  });

  test("a running job renders the four named research stages", async ({ page }) => {
    const server = makeServer(samplePayload({ enabled: true, error: null }));
    server.job = bottleneckJob({
      stages: [
        { key: "refresh_skill", label: "Refresh skill", status: "done", note: null },
        { key: "read_lens", label: "Read lens", status: "running", note: null },
        { key: "draft", label: "Draft thesis", status: "pending", note: null },
        { key: "warm_metrics", label: "Pull market data", status: "pending", note: null },
      ],
    });
    await mockApi(page);
    await mockSection(page, server);
    await page.route("**/api/bottleneck/jobs", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([server.job]) })
    );
    await boot(page);

    const panel = page.locator(".bn-job");
    await expect(panel).toContainText("Drafting a topic for");
    // All four frozen stages, in order, labelled straight from the payload.
    const rows = panel.locator(".bn-stage");
    await expect(rows).toHaveCount(4);
    await expect(panel.locator(".bn-stage-label")).toHaveText([
      "Refresh skill", "Read lens", "Draft thesis", "Pull market data",
    ]);
    // Status alone drives the row state.
    await expect(rows.nth(0)).toHaveClass(/\bdone\b/);
    await expect(rows.nth(1)).toHaveClass(/\brunning\b/);
    await expect(rows.nth(2)).toHaveClass(/\bpending\b/);
    // Stages replace the bar; Cancel stays available while running.
    await expect(panel.locator(".bn-progress")).toHaveCount(0);
    await expect(panel.locator('[data-bn-action="cancel-job"]')).toBeVisible();
  });

  test("a skipped or failed stage shows its note, not an ambiguous hang", async ({ page }) => {
    const server = makeServer(samplePayload({ enabled: true, error: null }));
    server.job = bottleneckJob({
      stages: [
        { key: "refresh_skill", label: "Refresh skill", status: "skipped", note: "skill repo unreachable; using the cached lens" },
        { key: "read_lens", label: "Read lens", status: "done", note: null },
        { key: "draft", label: "Draft thesis", status: "done", note: null },
        { key: "warm_metrics", label: "Pull market data", status: "failed", note: "market data unavailable" },
      ],
    });
    await mockApi(page);
    await mockSection(page, server);
    await page.route("**/api/bottleneck/jobs", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([server.job]) })
    );
    await boot(page);

    const skipped = page.locator(".bn-stage.skipped");
    await expect(skipped).toHaveCount(1);
    await expect(skipped.locator(".bn-stage-note")).toHaveText("skill repo unreachable; using the cached lens");

    const failed = page.locator(".bn-stage.failed");
    await expect(failed).toHaveCount(1);
    await expect(failed.locator(".bn-stage-note")).toHaveText("market data unavailable");
  });

  test("export shows the importable document; import reports applied and skipped", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);

    await page.locator('.bn-toolbar [data-bn-action="export"]').click();
    const exportText = page.locator(".bn-export-text");
    await expect(exportText).toBeVisible();
    await expect(exportText).toHaveValue(/"version": 1/);
    await expect(exportText).toHaveValue(/"Grid power for data centers"/);
    await page.locator('[data-bn-action="close-panel"]').click();

    await page.locator('.bn-toolbar [data-bn-action="import"]').click();
    const importForm = page.locator('form[data-bn-form="import"]');
    await importForm.locator("textarea[data-field='doc']").fill('{"version": 1, "topics": [{"name": "Imported theme"}]}');
    await importForm.locator('button[type="submit"]').click();

    await expect.poll(() => server.calls.import).toEqual([{ version: 1, topics: [{ name: "Imported theme" }] }]);
    const notice = page.locator(".bn-msg.error");
    await expect(notice).toContainText("Imported 1 topic(s)");
    await expect(notice).toContainText("name is required");
  });

  test("Refresh skill reports a non-zero outcome instead of throwing", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await page.route("**/api/bottleneck/skill/refresh", (route) =>
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ ok: false, command: "npx -y skills add ...", returncode: 1, output_tail: "npm ERR! network", timed_out: false }),
      })
    );
    await boot(page);

    await page.locator('[data-bn-action="refresh-skill"]').click();
    const result = page.locator(".bn-skill-result");
    await expect(result).toHaveClass(/bad/);
    await expect(result).toContainText("did not complete");
    await expect(result).toContainText("Exit code 1");
    await expect(result).toContainText("npm ERR! network");
  });

  test("editing a topic sends the structured patch without duplicating rows", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);
    await page.locator('.bn-topic[data-topic-id="t1"] .bn-topic-toggle').click();
    await page.locator('[data-bn-action="edit-topic"]').click();

    const editor = page.locator(".bn-editor");
    await expect(editor).toBeVisible();
    // One row per stored item — the remove buttons carry the same data-index
    // attributes, so a naive read-back would duplicate every row.
    await expect(editor.locator(".bn-ed-layer")).toHaveCount(2);
    await expect(editor.locator('.bn-ed-stock[data-kind="anchor"]')).toHaveCount(2);
    await expect(editor.locator('.bn-ed-stock[data-kind="underdog"]')).toHaveCount(3);
    await expect(editor.locator('.bn-ed-stock[data-kind="underdog"]').nth(0).locator(".bn-ed-ev")).toHaveCount(2);

    await editor.locator(".bn-ed-grid").first().locator('input[data-field="name"]').fill("Grid power (edited)");
    await editor.locator('button[type="submit"]').click();

    await expect.poll(() => server.calls.update).toHaveLength(1);
    const patch = server.calls.update[0].patch;
    expect(server.calls.update[0].id).toBe("t1");
    expect(patch.name).toBe("Grid power (edited)");
    expect(patch.upstream).toHaveLength(2);
    expect(patch.upstream[0].stocks).toEqual(["ETN", "POWL"]);
    expect(patch.downstream.anchor).toHaveLength(2);
    expect(patch.downstream.underdogs).toHaveLength(3);
    expect(patch.downstream.anchor[0].ticker).toBe("VRT");
    expect(patch.downstream.anchor[0].evidence).toHaveLength(1);
    expect(patch.downstream.underdogs[0].evidence).toHaveLength(2);
    // The editor never sends ceiling as a string.
    expect(typeof patch.underdog_ceiling).toBe("number");
  });

  test("a 400 from update shows the validator's own messages", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await page.route("**/api/bottleneck/topics/t1", (route) => {
      if (route.request().method() !== "PUT") return route.fallback();
      route.fulfill({
        status: 400, contentType: "application/json",
        body: JSON.stringify({ detail: ["name is required and must be a non-empty string", "underdog_ceiling must be a number, got 'ten'"] }),
      });
    });
    await boot(page);
    await page.locator('.bn-topic[data-topic-id="t1"] .bn-topic-toggle').click();
    await page.locator('[data-bn-action="edit-topic"]').click();
    const editor = page.locator(".bn-editor");
    await editor.locator('input[data-field="underdog_ceiling"]').fill("ten");
    await editor.locator(".bn-ed-grid").first().locator('input[data-field="name"]').fill("Grid power (edited)");
    await editor.locator('button[type="submit"]').click();

    const msg = editor.locator("[data-bn-msg]");
    await expect(msg).toContainText("name is required");
    await expect(msg).toContainText("underdog_ceiling must be a number");
  });

  test("delete asks for confirmation and then removes the topic", async ({ page }) => {
    const server = makeServer(samplePayload());
    await mockApi(page);
    await mockSection(page, server);
    await boot(page);
    await page.locator('.bn-topic[data-topic-id="t1"] .bn-topic-toggle').click();

    await page.locator('[data-bn-action="delete-topic"]').click();
    await expect(page.locator('[data-bn-action="confirm-delete"]')).toBeVisible();
    expect(server.calls.delete).toHaveLength(0);

    await page.locator('[data-bn-action="confirm-delete"]').click();
    await expect.poll(() => server.calls.delete).toEqual(["t1"]);
  });

  // ---- Coverage badge (section-payload sourced, not dashboard) --------------
  // The card header badge must count the same `bottleneck.topics` the body
  // renders. The mocked dashboard coverage is made to disagree on purpose: if
  // the badge ever falls back to the dashboard map, these assertions fail.

  test("coverage badge counts the section payload, not the dashboard", async ({ page }) => {
    const payload = samplePayload();
    // A topic whose layers have no momentum yet: only 1 of 3 layers warmed.
    // The body would show dashes for the two cold layers.
    payload.bottleneck.topics[0].upstream = [
      { name: "Transformers", physical_constraint: "Lead times run past 2027", what_to_watch: "Order backlog", stocks: ["ETN"], roc_40d_pct: null, as_of: AS_OF },
      { name: "Switchgear", physical_constraint: "Qualified capacity is thin", what_to_watch: "Book-to-bill", stocks: [], roc_40d_pct: null, as_of: AS_OF },
      { name: "Copper", physical_constraint: "Smelter capacity", what_to_watch: "Treatment charges", stocks: ["FCX"], roc_40d_pct: 4.2, as_of: AS_OF },
    ];
    payload.bottleneck.strongest_signal = {
      name: "Copper", physical_constraint: "Smelter capacity", what_to_watch: "Treatment charges",
      stocks: ["FCX"], roc_40d_pct: 4.2, as_of: AS_OF, topic_id: "t1", topic_name: "Grid power for data centers",
    };
    const server = makeServer(payload);
    // Dashboard reports the section complete (0/0) -> the old dashboard-sourced
    // badge would render nothing at all. The section payload says 1/3.
    await installMockDashboard(page, { coverage: { bottleneck: { ok: 0, total: 0 } } });
    await mockSection(page, server);
    await boot(page);

    const badge = page.locator('[data-card="bottleneck"] h2 .cov-badge');
    await expect(badge).toHaveCount(1);
    await expect(badge).toHaveText("1/3");
    await expect(badge).toHaveAttribute("title", /1 of 3 upstream layers have momentum/);
  });

  test("a fully-warmed topic shows no coverage badge", async ({ page }) => {
    const payload = samplePayload();
    for (const layer of payload.bottleneck.topics[0].upstream) layer.roc_40d_pct = 5.0;
    const server = makeServer(payload);
    // Dashboard claims the section is incomplete (1/2) -> an old badge would
    // show "1/2". A complete section payload must render no badge.
    await installMockDashboard(page, { coverage: { bottleneck: { ok: 1, total: 2 } } });
    await mockSection(page, server);
    await boot(page);

    await expect(page.locator('[data-card="bottleneck"] h2 .cov-badge')).toHaveCount(0);
  });

  test("an empty section shows no coverage badge and does not crash", async ({ page }) => {
    const server = makeServer({
      topics: [],
      bottleneck: { as_of: AS_OF, framework: "serenity-aleabitoreddit", thesis: "t", topics: [], strongest_signal: null, note: "empty" },
      generation: { enabled: true, error: null },
    });
    // Dashboard claims 0/3 -> an old badge would show "0/3". No topics means
    // total === 0, so nothing renders and the section stays standing.
    await installMockDashboard(page, { coverage: { bottleneck: { ok: 0, total: 3 } } });
    await mockSection(page, server);
    await boot(page);

    await expect(page.locator(".bn-empty")).toBeVisible();
    await expect(page.locator('[data-card="bottleneck"] h2 .cov-badge')).toHaveCount(0);
    await expect(page.locator("#bottleneckBody .bn-msg.error")).toHaveCount(0);
  });
});
