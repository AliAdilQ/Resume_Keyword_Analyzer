/* Genuine screenshots and smoke checks against the locally running Flask app.
 * Uses fictional seeded accounts. Its temporary analysis is deleted via the UI.
 */
"use strict";
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const appUrl = process.env.APP_URL || "http://127.0.0.1:5000";
const output = path.join(root, "screenshots");
const errors = [];
const visited = new Set();

async function settle(page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(650); // Let Chart.js finish its first animation.
}

async function visit(page, route) {
  const response = await page.goto(appUrl + route);
  assert.equal(response.status(), 200, `${route} should load`);
  await settle(page);
  visited.add(route);
}

async function capture(page, name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true });
  console.log(`Captured screenshots/${name}`);
}

async function signIn(page, username, password) {
  await visit(page, "/login");
  await page.locator("#identity").fill(username);
  await page.locator("#password").fill(password);
  try {
    await Promise.all([
      page.waitForURL(/dashboard/),
      page.getByRole("button", { name: /^Sign in/ }).click(),
    ]);
  } catch (error) {
    throw new Error(
      `Sign-in failed: ${await page.locator("main").innerText()}. ${error.message}`,
    );
  }
  await settle(page);
}

function watch(page) {
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("response", (response) => {
    if (
      response.url().startsWith(appUrl + "/static/") &&
      response.status() >= 400
    ) {
      errors.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("dialog", (dialog) => dialog.accept());
}

async function assertCharts(page, expected) {
  const count = await page.evaluate(
    () =>
      Array.from(document.querySelectorAll("canvas")).filter(
        (canvas) => typeof Chart !== "undefined" && Chart.getChart(canvas),
      ).length,
  );
  assert.equal(count, expected, "Expected real initialized charts");
}

async function mobileCheck(page, routes) {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of routes) {
    await visit(page, route);
    const dimensions = await page.evaluate(() => ({
      content: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
    }));
    assert(
      dimensions.content <= dimensions.viewport + 1,
      `${route}: mobile horizontal overflow`,
    );
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

(async () => {
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.CHROMIUM_EXECUTABLE }
      : {}),
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    watch(page);
    await visit(page, "/");
    assert(
      await page
        .locator(".brand")
        .textContent()
        .then((value) => value.includes("ResumeLens")),
      "APP_URL must point to Resume Keyword Analyzer",
    );
    await capture(page, "home.png");
    await visit(page, "/about");
    await visit(page, "/register");
    await mobileCheck(page, ["/", "/about", "/register", "/login"]);

    await signIn(page, "demo_user", "Demo@123");
    await assertCharts(page, 1);
    await capture(page, "user_dashboard.png");
    await visit(page, "/analyze");
    await page
      .locator("#resume")
      .setInputFiles(path.join(root, "sample_data", "sample_resume.txt"));
    await page.locator("#load-sample").click();
    await page.waitForFunction(
      () => document.querySelector("#job_description").value.length > 20,
    );
    await capture(page, "analyzer.png");
    await Promise.all([
      page.waitForURL(/\/analysis\/\d+$/),
      page.getByRole("button", { name: /Analyze resume/ }).click(),
    ]);
    await settle(page);
    const temporaryPath = new URL(page.url()).pathname;
    await assertCharts(page, 3);
    assert(
      await page.locator("#result-data").count(),
      "Saved real result should render",
    );
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("link", { name: /Download report/ }).click();
    const download = await downloadPromise;
    assert(
      download.suggestedFilename().endsWith(".txt"),
      "Text report should download",
    );
    await capture(page, "result.png");
    await mobileCheck(page, [
      "/dashboard",
      "/analyze",
      "/history",
      temporaryPath,
    ]);

    await visit(page, "/history");
    const analysisId = temporaryPath.split("/").pop();
    await Promise.all([
      page.waitForURL(/\/history$/),
      page
        .locator(`form[action='/analysis/${analysisId}/delete'] button`)
        .click(),
    ]);
    await settle(page);
    const remaining = await page.locator(`a[href='${temporaryPath}']`).count();
    assert.equal(remaining, 0, "Temporary analysis should be deleted");

    const adminContext = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      reducedMotion: "reduce",
    });
    const admin = await adminContext.newPage();
    watch(admin);
    await signIn(admin, "admin", "Admin@123");
    await assertCharts(admin, 1);
    await capture(admin, "admin_dashboard.png");
    await visit(admin, "/admin/users?q=demo");
    assert(
      await admin.getByRole("link", { name: "demo_user", exact: true }).count(),
    );
    const details = await admin
      .getByRole("link", { name: /^Details/ })
      .first()
      .getAttribute("href");
    await visit(admin, details);
    await visit(admin, "/admin/analyses?q=Python&min_score=0&max_score=100");
    assert(
      await admin
        .getByRole("link", { name: "Python Developer", exact: true })
        .count(),
    );
    await mobileCheck(admin, [
      "/admin/dashboard",
      "/admin/users",
      "/admin/analyses",
      details,
    ]);
    await Promise.all([
      admin.waitForURL(appUrl + "/"),
      admin.getByRole("button", { name: "Sign out", exact: true }).click(),
    ]);
    await settle(admin);
    assert.equal(errors.length, 0, "Browser errors: " + errors.join("; "));
    console.log(
      `Browser checks passed: ${visited.size} routes, real upload/download/deletion, 5 charts, desktop and mobile layouts. No browser errors or missing local assets.`,
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
