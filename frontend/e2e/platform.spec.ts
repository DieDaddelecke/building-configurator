import { expect, test } from "@playwright/test";

// Voraussetzung: Konto ops@emprise.local ist freigeschaltet
//   docker compose exec api python -m app.cli staff-add ops@emprise.local ops

test("Startseite folgt der Browsersprache und wechselt auf Französisch", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") violations.push(msg.text());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Was Sie auf Ihrem Grundstück bauen dürfen");
  await page.getByRole("button", { name: "FR", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Ce que vous pouvez construire sur votre parcelle");
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  expect(violations, "keine Konsolenfehler, insbesondere keine CSP-Verstöße").toEqual([]);
});

test("Büro: Anmeldung über OIDC mit MFA, Startseite, Abmeldung", async ({ page }) => {
  await page.goto("/buero");
  await page.getByRole("link", { name: "Anmelden" }).click();
  await expect(page).toHaveURL(/\/buero$/);
  await expect(page.getByRole("heading", { name: "Willkommen" })).toBeVisible();
  await expect(page.getByText("ops", { exact: false }).first()).toBeVisible();

  await page.getByRole("button", { name: "Abmelden" }).click();
  await expect(page.getByRole("link", { name: "Anmelden" })).toBeVisible();
});

test("API: Gesundheit und Fehlerformat", async ({ request }) => {
  const ready = await request.get("/api/health/ready");
  expect(ready.status()).toBe(200);
  expect((await ready.json()).postgis).toBeTruthy();

  const missing = await request.get("/api/v1/gibt-es-nicht");
  expect(missing.status()).toBe(404);
  expect(missing.headers()["content-type"]).toContain("application/problem+json");
});
