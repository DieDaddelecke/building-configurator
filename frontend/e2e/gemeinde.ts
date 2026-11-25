import { expect, type Page } from "@playwright/test";

/**
 * Treillières für die Parzellennummer wählen. Das Auswahlfeld gibt es erst ab zwei Gemeinden im Einzugsgebiet
 * (ParzellenWahl); in CI gibt es nur Treillières, ein lokaler Stack kann weitere haben.
 */
export async function waehleTreillieres(page: Page): Promise<void> {
  // Freigegeben, sobald das Einzugsgebiet geladen und eine Gemeinde gesetzt ist
  await expect(page.getByRole("button", { name: "Parzelle suchen" })).toBeEnabled();
  const gemeinde = page.getByLabel("Gemeinde");
  if ((await gemeinde.count()) > 0) {
    await gemeinde.selectOption({ label: "TREILLIERES" });
  }
}
