import createClient, { type Middleware } from "openapi-fetch";

import { currentLanguage } from "../i18n";
import type { paths } from "./schema";

const CSRF_COOKIE = "emprise_csrf";

function readCookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

// Sprache und CSRF-Token an jeden Aufruf; Frontend und API teilen sich die Domain (Plan 6.2)
const platformHeaders: Middleware = {
  onRequest({ request }) {
    request.headers.set("Accept-Language", currentLanguage());
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      const token = readCookie(CSRF_COOKIE);
      if (token) request.headers.set("X-CSRF-Token", token);
    }
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: window.location.origin, credentials: "same-origin" });
api.use(platformHeaders);

/** Fehler nach RFC 9457 aus der API (Spez. 6.1). */
export interface Problem {
  status: number;
  code: string;
  title: string;
  detail?: string;
  request_id?: string | null;
}

export class ApiError extends Error {
  constructor(readonly problem: Problem) {
    super(problem.title);
  }
}

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const problem = (result.error as Problem | undefined) ?? {
      status: result.response.status,
      code: "unexpected_response",
      title: result.response.statusText,
    };
    throw new ApiError(problem);
  }
  return result.data;
}
