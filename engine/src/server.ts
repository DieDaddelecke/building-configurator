// Start des Rechendienstes; Port 8090, nur im Compose-Netz (docs/PLAN_HAUSMODELL.md 3.3).
import { createServer } from "node:http";
import { createHandler } from "./app.ts";

const port = Number(process.env.PORT ?? 8090);
const handler = createHandler({ release: process.env.EMPRISE_RELEASE ?? "dev" });
const server = createServer((req, res) => void handler(req, res));
server.requestTimeout = 30_000;
server.headersTimeout = 10_000;

server.listen(port, "0.0.0.0", () => {
  process.stdout.write(`${JSON.stringify({ time: new Date().toISOString(), level: "info", event: "listening", port })}\n`);
});

for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
