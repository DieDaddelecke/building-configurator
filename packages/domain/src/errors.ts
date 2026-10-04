// Strukturierte Fehler des Kerns: Eingaben, die sich nicht rechnen lassen (unbekannte Werte, nicht unterstützte
// Formen). Prüfergebnisse zu einer gültigen Eingabe sind dagegen RuleResults (P 6.6, P 8.3).
import type { ModelErrorCode } from "./codes.ts";

export class ModelError extends Error {
  readonly code: ModelErrorCode;
  readonly detail: Readonly<Record<string, string>>;

  constructor(code: ModelErrorCode, detail: Record<string, string> = {}) {
    super(Object.keys(detail).length ? `${code} ${JSON.stringify(detail)}` : code);
    this.code = code;
    this.detail = detail;
  }
}
