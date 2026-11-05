/* Read-only public gateway smoke check. No generation or data mutation. */
const { chromium } = require("playwright");
const assert = require("node:assert/strict");

class GatewaySmoke {
  async run() {
    const browser = await chromium.launch({
      headless: true,
      executablePath:
        process.env.MATHPDF_CHROMIUM_EXECUTABLE || chromium.executablePath(),
    });
    try {
      const page = await browser.newPage({
        viewport: { width: 390, height: 844 },
      });
      const base = process.env.MATHPDF_FRONTEND_URL || "http://127.0.0.1:8770";
      const health = await page.request.get(base + "/health");
      assert.equal(health.status(), 200);
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(base);
      await page.waitForLoadState("networkidle");
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      assert.deepEqual(errors, []);
      console.log("Gateway page and mobile width checks passed.");
    } finally {
      await browser.close();
    }
  }
}
new GatewaySmoke().run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
