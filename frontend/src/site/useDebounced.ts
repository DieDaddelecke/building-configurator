import { useEffect, useState } from "react";

/** Wert erst nach einer Pause übernehmen, z. B. Adressvorschläge nach dem Tippen (Rate-Limit, Kosten beim Anbieter). */
export function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
