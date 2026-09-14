import type { ReactNode } from "react";

export function Kopf({ eyebrow, titel, children, gross }: { eyebrow?: string; titel: string; children?: ReactNode; gross?: boolean }) {
  return (
    <div className="flex flex-col gap-3">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      {gross ? (
        <h1 className="f-display text-4xl lg:text-5xl font-semibold t-ink balance">{titel}</h1>
      ) : (
        <h2 className="f-display text-3xl lg:text-4xl font-semibold t-ink balance">{titel}</h2>
      )}
      {children && <div className="t-mute max-w-prose">{children}</div>}
    </div>
  );
}
