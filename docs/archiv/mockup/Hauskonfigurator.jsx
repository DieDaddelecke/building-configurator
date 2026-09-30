import React, { useState, useMemo, useRef, useEffect } from "react";

/* =====================================================================
   EMPRISE — Klickbares Mockup des Hauskonfigurators
   Prototyp zum Vorführen. Alle Daten fest hinterlegt, Zustand nur im
   React-State. Datenblock zuerst, Darstellung darunter.
   ===================================================================== */

/* ---------------------------------------------------------------------
   DATEN (exakt aus der Vorgabe übernommen)
   --------------------------------------------------------------------- */

const PARZELLE = {
  adresse: "12 rue des Tilleuls, 44119 Treillières",
  kennung: "AB 0147",
  flaeche_m2: 612,
  strassenfront_m: 20,
  tiefe_m: 31,
  strassenseite: "Norden",
  gartenseite: "Sueden",
  nachbarn_bebaut: ["Osten", "Westen"],
};

const REGELWERK = {
  zone: "UB — zone urbaine à vocation résidentielle",
  max_geschosse: "R+1+C",
  max_firsthoehe_m: 9.0,
  max_traufhoehe_m: 6.0,
  grundflaechenzahl_prozent: 40,
  max_grundflaeche_m2: 244.8,
  abstand_strasse_m: 5.0,
  abstand_seitlich_m: 3.0,
  abstand_hinten_m: 5.0,
  unversiegelt_min_prozent: 30,
  unversiegelt_min_m2: 183.6,
  dachformen_zulaessig: ["Satteldach 35°–45°", "Walmdach"],
  dachformen_unzulaessig: ["Flachdach als Hauptdach"],
  fassaden_zulaessig: ["helle Putztöne", "Naturholz", "Ziegel"],
  fassaden_unzulaessig: ["grelle Farben"],
};

const BEBAUBARE_FLAECHE = {
  breite_m: 14.0,
  tiefe_m: 21.0,
  hinweis: "Ergebnis der Abstandsregeln, wird auf der Parzelle hervorgehoben",
};

const ENERGIE = {
  klimazone: "H2b",
  norm: "RE2020",
  kennwert: "Bbio-Schwellenwert",
  befund: "Linie Base verfehlt den Schwellenwert knapp",
  aufpreis_konformitaet_eur: 9500,
  aufpreis_umfang: "verstärkte Dämmung und kontrollierte Lüftung",
};

const HAUSTYPEN = [
  {
    id: "ligne",
    name: "Ligne",
    kubatur: "kompakter Baukörper, R+1",
    grundflaeche_m2: 96,
    abmessung_m: [12.0, 8.0],
    wohnflaeche_m2: 158,
    zimmer: "4 Zimmer, 1 Bad + 1 Gäste-WC",
    dach: "Satteldach 40°, First längs",
    firsthoehe_m: 8.4,
    traufhoehe_m: 5.6,
    basispreis_eur: [328000, 362000],
    status: "zulaessig",
  },
  {
    id: "plateau",
    name: "Plateau",
    kubatur: "breit gelagert, eingeschossig mit Teilobergeschoss",
    grundflaeche_m2: 132,
    abmessung_m: [16.5, 8.0],
    wohnflaeche_m2: 141,
    zimmer: "4 Zimmer, 2 Bäder",
    dach: "Flachdach mit Attika",
    firsthoehe_m: 6.8,
    basispreis_eur: [341000, 379000],
    status: "gesperrt",
    sperrgruende: [
      "Flachdach als Hauptdach ist in Zone UB unzulässig",
      "Gebäudebreite 16,5 m überschreitet die bebaubare Breite von 14,0 m",
    ],
  },
  {
    id: "plateau_adapte",
    name: "Plateau — angepasst",
    kubatur: "breit gelagert, angepasste Variante",
    grundflaeche_m2: 108,
    abmessung_m: [13.5, 8.0],
    wohnflaeche_m2: 132,
    zimmer: "4 Zimmer, 2 Bäder",
    dach: "Satteldach 38°",
    firsthoehe_m: 8.1,
    basispreis_eur: [334000, 368000],
    status: "zulaessig",
    hinweis: "Erscheint als Vorschlag direkt an der gesperrten Karte Plateau",
  },
];

const LINIEN = [
  {
    id: "base",
    name: "Base",
    aufpreis_eur: 0,
    aufpreis_text: "enthalten im Basispreis",
    umfang: [
      "Fassade Putz weißgrau",
      "Fenster Kunststoff dreifach",
      "Boden Vinyl",
      "Sanitär Standardserie",
      "Heizung Luft-Wasser-Wärmepumpe",
      "Dach Betondachstein anthrazit",
    ],
  },
  {
    id: "confort",
    name: "Confort",
    aufpreis_eur: 34000,
    umfang: [
      "Fassade Putz durchgefärbt",
      "Fenster Holz-Alu",
      "Boden Eiche-Fertigparkett",
      "Sanitär gehobene Serie, bodengleiche Dusche",
      "Heizung Wärmepumpe mit Fußbodenheizung",
      "Dach Tonziegel",
    ],
  },
  {
    id: "signature",
    name: "Signature",
    aufpreis_eur: 71000,
    umfang: [
      "Fassade Naturholz vorvergraut",
      "Fenster Holz-Alu bodentief",
      "Boden Massivholzdiele",
      "Sanitär Designserie",
      "Heizung Wärmepumpe, Fußbodenheizung, kontrollierte Lüftung",
      "Dach Tonziegel handgeformt",
      "Photovoltaik 6 kWp",
    ],
  },
];

const OPTIONEN = [
  { id: "holz_sued", name: "Holzverschalung Lärche statt Putz (Südfassade)", aufpreis_eur: 12400, enthalten_in: ["signature"] },
  { id: "holz_voll", name: "Vollflächige Holzverschalung", aufpreis_eur: 28900, enthalten_in: ["signature"] },
  { id: "ziegel_eg", name: "Ziegelsichtmauerwerk Erdgeschoss", aufpreis_eur: 19700, enthalten_in: [] },
  { id: "ziegel_dach", name: "Dachziegel Tonziegel naturrot statt anthrazit", aufpreis_eur: 4200, enthalten_in: ["confort", "signature"] },
  { id: "fenster_sued", name: "Fenster bodentief Südseite", aufpreis_eur: 8600, enthalten_in: ["signature"] },
  { id: "carport", name: "Carport zweistellig", aufpreis_eur: 14500, enthalten_in: [] },
  { id: "keller", name: "Keller unter halber Grundfläche", aufpreis_eur: 47000, enthalten_in: [] },
  { id: "pv", name: "Photovoltaik 6 kWp", aufpreis_eur: 11200, enthalten_in: ["signature"] },
  { id: "terrasse", name: "Terrasse Holz 24 m²", aufpreis_eur: 9800, enthalten_in: [] },
];

const KONTAKTFORMULAR = [
  "Name", "E-Mail", "Telefon", "gewünschter Baubeginn", "Finanzierung geklärt (ja/nein)",
];

/* ---------------------------------------------------------------------
   DARSTELLUNGSKONSTANTEN (keine Fachdaten — Gliederung, Farben, Texte)
   --------------------------------------------------------------------- */

const MARKE = "Emprise";

const SCHRITTE = [
  { nr: 1, kurz: "Adresse" },
  { nr: 2, kurz: "Parzelle" },
  { nr: 3, kurz: "Regelwerk" },
  { nr: 4, kurz: "Haustyp" },
  { nr: 5, kurz: "Linie" },
  { nr: 6, kurz: "Optionen" },
  { nr: 7, kurz: "Implantation" },
  { nr: 8, kurz: "Vorentwurf" },
  { nr: 9, kurz: "Kontakt" },
];

// Optische Gliederung der Optionsliste
const OPTION_GRUPPEN = [
  { titel: "Fassade", ids: ["holz_sued", "holz_voll", "ziegel_eg"] },
  { titel: "Dach", ids: ["ziegel_dach", "pv"] },
  { titel: "Fenster", ids: ["fenster_sued"] },
  { titel: "Außenanlagen", ids: ["terrasse", "carport"] },
  { titel: "Rohbau", ids: ["keller"] },
];

// Entscheidung: die beiden Holzverschalungen schließen sich gegenseitig aus
const AUSSCHLUESSE = { holz_sued: ["holz_voll"], holz_voll: ["holz_sued"] };

// Materialfarben für die Axonometrie (Farbflächen statt Produktfotos)
const MATERIAL = {
  putz_weissgrau: { name: "Putz weißgrau", farbe: "#E6E4DD", textur: "putz" },
  putz_durchgefaerbt: { name: "Putz durchgefärbt", farbe: "#D8C8AE", textur: "putz" },
  holz_vorvergraut: { name: "Naturholz vorvergraut", farbe: "#AAA397", linie: "#8C857A", textur: "holz" },
  laerche: { name: "Lärche", farbe: "#BF8E5E", linie: "#9C7046", textur: "holz" },
  ziegel: { name: "Ziegelsichtmauerwerk", farbe: "#A85D42", linie: "#8A4A33", textur: "ziegel" },
  dach_anthrazit: { name: "Betondachstein anthrazit", farbe: "#4C4F53", linie: "#3A3D40" },
  dach_ton: { name: "Tonziegel", farbe: "#B45D3E", linie: "#944A31" },
  dach_ton_hand: { name: "Tonziegel handgeformt", farbe: "#9F5339", linie: "#81422D" },
  dach_naturrot: { name: "Tonziegel naturrot", farbe: "#B9583A", linie: "#96462E" },
  pv: { name: "Photovoltaik", farbe: "#2E3844", linie: "#56616E" },
  glas: { farbe: "#A9BBC6" },
  terrasse: { name: "Holzdeck", farbe: "#C9A57B", linie: "#A8845B" },
};

// Aus den Daten abgeleitete Geometrie (Meter, Ursprung = Nordwest-Ecke der Parzelle)
const PARZ_B = PARZELLE.strassenfront_m;
const PARZ_T = PARZELLE.tiefe_m;
const BAUFELD = {
  x: REGELWERK.abstand_seitlich_m,
  y: REGELWERK.abstand_strasse_m,
  b: BEBAUBARE_FLAECHE.breite_m,
  t: BEBAUBARE_FLAECHE.tiefe_m,
};
const MAX_TYPBREITE = Math.max(...HAUSTYPEN.map((t) => t.abmessung_m[0]));
const RASTER_M = 0.25;
const TERRASSE_MASS = [8, 3]; // 24 m² als 8 × 3 m dargestellt

/* ---------------------------------------------------------------------
   HILFSFUNKTIONEN
   --------------------------------------------------------------------- */

const zahl = (n, d = 0) =>
  Number(n).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
const eur = (n) => `${zahl(n)} €`;
const rund = (n) => Math.round(n / 1000) * 1000;
const caEur = (n) => `ca. ${eur(rund(n))}`;
const caDiff = (n) => `+ ca. ${eur(n)}`;
const meter = (n, d = 1) => `${zahl(n, d)} m`;
const typNach = (id) => HAUSTYPEN.find((t) => t.id === id) || null;
const linieNach = (id) => LINIEN.find((l) => l.id === id) || null;
const optionNach = (id) => OPTIONEN.find((o) => o.id === id);
const enthalten = (opt, linieId) => !!linieId && opt.enthalten_in.includes(linieId);
const umfangTeilen = (s) => {
  const i = s.indexOf(" ");
  return [s.slice(0, i), s.slice(i + 1)];
};

function korridorBerechnen({ schritt, typId, linieId, optionen }) {
  const typ = typNach(typId);
  if (!typ) {
    if (schritt < 3) return { leer: true };
    const zul = HAUSTYPEN.filter((t) => t.status === "zulaessig");
    return {
      lo: Math.min(...zul.map((t) => t.basispreis_eur[0])),
      hi: Math.max(...zul.map((t) => t.basispreis_eur[1])),
      posten: [{ label: `Spanne der ${zul.length} zulässigen Haustypen`, text: "" }],
      vorlaeufig: true,
    };
  }
  const linie = linieNach(linieId);
  const posten = [{ label: typ.name, text: `${eur(typ.basispreis_eur[0])} – ${eur(typ.basispreis_eur[1])}` }];
  let diff = 0;
  if (linie) {
    diff += linie.aufpreis_eur;
    posten.push({ label: `Linie ${linie.name}`, text: linie.aufpreis_eur ? caDiff(linie.aufpreis_eur) : "enthalten" });
    if (linie.id === "base") {
      diff += ENERGIE.aufpreis_konformitaet_eur;
      posten.push({ label: "RE2020-Konformität", text: caDiff(ENERGIE.aufpreis_konformitaet_eur), warn: true });
    }
  }
  const berechnet = optionen.map(optionNach).filter((o) => !enthalten(o, linieId));
  const optSumme = berechnet.reduce((s, o) => s + o.aufpreis_eur, 0);
  if (berechnet.length) {
    diff += optSumme;
    posten.push({
      label: berechnet.length === 1 ? "1 Option" : `${berechnet.length} Optionen`,
      text: caDiff(optSumme),
    });
  }
  return { lo: typ.basispreis_eur[0] + diff, hi: typ.basispreis_eur[1] + diff, posten };
}

// Grundriss-Maße in Planlage (b = Ost-West, t = Nord-Süd)
function planMass(typ, gedreht) {
  const [a, b] = typ.abmessung_m;
  return gedreht ? { b, t: a } : { b: a, t: b };
}

const REGEL_TEXT = {
  strasse: `Abstand zur Straße mind. ${meter(REGELWERK.abstand_strasse_m)}`,
  west: `Seitlicher Abstand West mind. ${meter(REGELWERK.abstand_seitlich_m)}`,
  ost: `Seitlicher Abstand Ost mind. ${meter(REGELWERK.abstand_seitlich_m)}`,
  hinten: `Abstand zur hinteren Grenze mind. ${meter(REGELWERK.abstand_hinten_m)}`,
};

function lageBegrenzen(lage, typ) {
  const m = planMass(typ, lage.gedreht);
  const minX = BAUFELD.x, maxX = BAUFELD.x + BAUFELD.b - m.b;
  const minY = BAUFELD.y, maxY = BAUFELD.y + BAUFELD.t - m.t;
  let verletzt = null;
  if (lage.y < minY - 1e-6) verletzt = "strasse";
  else if (lage.y > maxY + 1e-6) verletzt = "hinten";
  else if (lage.x < minX - 1e-6) verletzt = "west";
  else if (lage.x > maxX + 1e-6) verletzt = "ost";
  return {
    lage: { ...lage, x: Math.min(maxX, Math.max(minX, lage.x)), y: Math.min(maxY, Math.max(minY, lage.y)) },
    verletzt,
  };
}

function voreinstellung(art, typ, gedreht) {
  if (art === "suedgarten") {
    return { x: BAUFELD.x, y: BAUFELD.y, gedreht: false };
  }
  const m = planMass(typ, gedreht);
  const x = (PARZ_B - m.b) / 2;
  if (art === "strassennah") return { x, y: BAUFELD.y, gedreht };
  return { x, y: BAUFELD.y + (BAUFELD.t - m.t) / 2, gedreht }; // zurückversetzt
}

function abstaende(lage, typ) {
  const m = planMass(typ, lage.gedreht);
  return {
    strasse: lage.y,
    hinten: PARZ_T - lage.y - m.t,
    west: lage.x,
    ost: PARZ_B - lage.x - m.b,
    ...m,
  };
}

// Welche Materialien sind bei aktueller Auswahl sichtbar?
function materialien(linieId, optionen) {
  const aktiv = (id) => optionen.includes(id) || enthalten(optionNach(id), linieId);
  let fassade = MATERIAL.putz_weissgrau;
  if (linieId === "confort") fassade = MATERIAL.putz_durchgefaerbt;
  if (linieId === "signature") fassade = MATERIAL.holz_vorvergraut;
  let fassadeSued = fassade;
  if (linieId !== "signature") {
    if (aktiv("holz_voll")) { fassade = MATERIAL.laerche; fassadeSued = MATERIAL.laerche; }
    else if (aktiv("holz_sued")) fassadeSued = MATERIAL.laerche;
  }
  let dach = MATERIAL.dach_anthrazit;
  if (linieId === "confort") dach = MATERIAL.dach_ton;
  if (linieId === "signature") dach = MATERIAL.dach_ton_hand;
  if (linieId === "base" && aktiv("ziegel_dach")) dach = MATERIAL.dach_naturrot;
  return {
    fassade, fassadeSued, dach,
    ziegelEG: aktiv("ziegel_eg"),
    bodentief: aktiv("fenster_sued"),
    rahmen: linieId === "confort" || linieId === "signature" ? "#4A4F4D" : "#F4F4F1",
    fensterName: linieId === "base" || !linieId ? "Kunststoff dreifach" : linieId === "confort" ? "Holz-Alu" : "Holz-Alu bodentief",
    pv: aktiv("pv"),
    terrasse: aktiv("terrasse"),
    carport: aktiv("carport"),
    keller: aktiv("keller"),
  };
}

/* ---------------------------------------------------------------------
   GESTALTUNG — Tokens, Schriften, wenige semantische Klassen.
   Layout und Abstände über Tailwind-Kernklassen.
   --------------------------------------------------------------------- */

const STIL = `
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root{
  --paper:#F3F4F1; --sheet:#FCFCFA; --ink:#1C2220; --mute:#59625E; --faint:#8B938F;
  --line:#D7DBD7; --line-strong:#B0B6B2; --accent:#2B45B0; --accent-tint:#E5E9F6; --accent-ink:#FFFFFF;
  --warn:#7D5300; --warn-tint:#F7EEDA; --alert:#9E3526; --alert-tint:#F6E6E2;
  --street:#E8EAE6; --house:#262C29; --hatch:#AEB4B0; --axo:#2A2F2D;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --paper:#111413; --sheet:#171B19; --ink:#E3E7E4; --mute:#A2ABA6; --faint:#737C77;
    --line:#2B322F; --line-strong:#454E4A; --accent:#8FA0F0; --accent-tint:#1D2442; --accent-ink:#0E1330;
    --warn:#E0B25C; --warn-tint:#2B2413; --alert:#EC8B7A; --alert-tint:#33201C;
    --street:#1E2321; --house:#C8CEC9; --hatch:#4F5854; --axo:#0C0F0E;
  }
}
:root[data-theme="dark"]{
  --paper:#111413; --sheet:#171B19; --ink:#E3E7E4; --mute:#A2ABA6; --faint:#737C77;
  --line:#2B322F; --line-strong:#454E4A; --accent:#8FA0F0; --accent-tint:#1D2442; --accent-ink:#0E1330;
  --warn:#E0B25C; --warn-tint:#2B2413; --alert:#EC8B7A; --alert-tint:#33201C;
  --street:#1E2321; --house:#C8CEC9; --hatch:#4F5854; --axo:#0C0F0E;
}
body{background:var(--paper);}
.emp{font-family:"IBM Plex Sans",ui-sans-serif,system-ui,"Segoe UI",sans-serif;color:var(--ink);background:var(--paper);-webkit-font-smoothing:antialiased;font-size:15px;line-height:1.55}
.f-display{font-family:"Archivo","Helvetica Neue",Arial,sans-serif;font-stretch:116%;letter-spacing:-0.012em;line-height:1.12}
.f-mono{font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace}
.num{font-variant-numeric:tabular-nums}
.balance{text-wrap:balance}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;font-size:11px;line-height:1.4;letter-spacing:.11em;text-transform:uppercase;color:var(--mute)}
.t-ink{color:var(--ink)} .t-mute{color:var(--mute)} .t-faint{color:var(--faint)} .t-accent{color:var(--accent)}
.t-warn{color:var(--warn)} .t-alert{color:var(--alert)} .t-on-accent{color:var(--accent-ink)}
.bg-paper{background:var(--paper)} .bg-sheet{background:var(--sheet)} .bg-tint{background:var(--accent-tint)}
.bg-accent{background:var(--accent)} .bg-warn{background:var(--warn-tint)} .bg-alert{background:var(--alert-tint)} .bg-street{background:var(--street)}
.bd{border-color:var(--line)} .bd-strong{border-color:var(--line-strong)} .bd-accent{border-color:var(--accent)}
.bd-warn{border-color:var(--warn)} .bd-alert{border-color:var(--alert)} .bd-ink{border-color:var(--ink)}
.btn{display:inline-flex;align-items:center;gap:.5rem;padding:.7rem 1.15rem;font-weight:500;font-size:14px;line-height:1.2;border:1px solid transparent;transition:background .15s,border-color .15s,color .15s}
.btn-primary{background:var(--accent);color:var(--accent-ink)}
.btn-primary:hover{filter:brightness(1.1)}
.btn-primary:disabled{background:var(--line);color:var(--faint);cursor:not-allowed;filter:none}
.btn-ghost{border-color:var(--line-strong);color:var(--ink);background:transparent}
.btn-ghost:hover{border-color:var(--ink)}
.btn-ghost:disabled{color:var(--faint);border-color:var(--line);cursor:not-allowed}
.chip{border:1px solid var(--line-strong);padding:.45rem .8rem;font-size:13px;color:var(--ink);background:var(--sheet)}
.chip:hover{border-color:var(--ink)}
.chip[aria-pressed="true"]{border-color:var(--accent);color:var(--accent);background:var(--accent-tint)}
.link{color:var(--accent);text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:1px}
.field{width:100%;background:var(--sheet);border:1px solid var(--line-strong);color:var(--ink);padding:.65rem .8rem;font-size:15px}
.field:focus{border-color:var(--accent);outline:none;box-shadow:0 0 0 1px var(--accent)}
.field[aria-invalid="true"]{border-color:var(--alert)}
.emp :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.karte{border:1px solid var(--line);background:var(--sheet);transition:border-color .15s}
.karte-wahl{cursor:pointer}
.karte-wahl:hover{border-color:var(--line-strong)}
.karte[aria-pressed="true"]{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
.kasten{display:inline-block;width:16px;height:16px;border:1.5px solid var(--line-strong);flex:none;position:relative;background:var(--sheet)}
.kasten[data-an="true"]{border-color:var(--accent);background:var(--accent)}
.kasten[data-an="true"]::after{content:"";position:absolute;left:4px;top:1px;width:5px;height:9px;border:solid var(--accent-ink);border-width:0 2px 2px 0;transform:rotate(45deg)}
.kasten[data-inkl="true"]{border-color:var(--mute);background:var(--line)}
.regel-zeile+.regel-zeile{border-top:1px solid var(--line)}
@keyframes zeichnen{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
@keyframes einblenden{from{opacity:0}to{opacity:1}}
@keyframes aufhellen{from{background:var(--accent-tint)}to{background:transparent}}
.anim-linie{stroke-dasharray:1;animation:zeichnen 1s cubic-bezier(.55,0,.2,1) both}
.anim-flaeche{animation:einblenden .8s ease-out .75s both}
.anim-text{animation:einblenden .5s ease-out 1.25s both}
.anim-seite{animation:einblenden .35s ease-out both}
.flash{animation:aufhellen 1.1s ease-out}
.greifbar{cursor:grab;touch-action:none}
.greifbar:active{cursor:grabbing}
@media (prefers-reduced-motion: reduce){.anim-linie,.anim-flaeche,.anim-text,.anim-seite,.flash{animation:none}}
`;

/* ---------------------------------------------------------------------
   ZEICHNUNGEN — Lageplan, Axonometrie, Skizzen (Inline-SVG, Einheit Meter)
   --------------------------------------------------------------------- */

const MONO = "IBM Plex Mono, ui-monospace, Consolas, monospace";
const txt = (farbe, groesse, extra = {}) => ({ fill: farbe, fontFamily: MONO, fontSize: groesse, ...extra });
const strich = (farbe, breite, extra = {}) => ({ stroke: farbe, strokeWidth: breite, fill: "none", ...extra });
const freistellen = { paintOrder: "stroke", stroke: "var(--sheet)", strokeWidth: 0.28, strokeLinejoin: "round" };

function MassH({ x1, x2, y, label, von, farbe = "var(--mute)", gr = 0.72 }) {
  const t = 0.32;
  return (
    <g>
      {von != null && (
        <>
          <line x1={x1} y1={von} x2={x1} y2={y + (y > von ? 0.4 : -0.4)} style={strich(farbe, 0.035)} />
          <line x1={x2} y1={von} x2={x2} y2={y + (y > von ? 0.4 : -0.4)} style={strich(farbe, 0.035)} />
        </>
      )}
      <line x1={x1} y1={y} x2={x2} y2={y} style={strich(farbe, 0.045)} />
      <line x1={x1 - t} y1={y + t} x2={x1 + t} y2={y - t} style={strich(farbe, 0.08)} />
      <line x1={x2 - t} y1={y + t} x2={x2 + t} y2={y - t} style={strich(farbe, 0.08)} />
      <text x={(x1 + x2) / 2} y={y - 0.3} textAnchor="middle" style={txt(farbe, gr, freistellen)}>{label}</text>
    </g>
  );
}

function MassV({ y1, y2, x, label, von, farbe = "var(--mute)", gr = 0.72 }) {
  const t = 0.32;
  const my = (y1 + y2) / 2;
  return (
    <g>
      {von != null && (
        <>
          <line x1={von} y1={y1} x2={x + (x > von ? 0.4 : -0.4)} y2={y1} style={strich(farbe, 0.035)} />
          <line x1={von} y1={y2} x2={x + (x > von ? 0.4 : -0.4)} y2={y2} style={strich(farbe, 0.035)} />
        </>
      )}
      <line x1={x} y1={y1} x2={x} y2={y2} style={strich(farbe, 0.045)} />
      <line x1={x - t} y1={y1 + t} x2={x + t} y2={y1 - t} style={strich(farbe, 0.08)} />
      <line x1={x - t} y1={y2 + t} x2={x + t} y2={y2 - t} style={strich(farbe, 0.08)} />
      <text x={x - 0.3} y={my} textAnchor="middle" transform={`rotate(-90 ${x - 0.3} ${my})`} style={txt(farbe, gr, freistellen)}>{label}</text>
    </g>
  );
}

function Schraffur({ id, farbe, abstand = 0.7, breite = 0.05 }) {
  return (
    <pattern id={id} patternUnits="userSpaceOnUse" width={abstand} height={abstand} patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2={abstand} style={strich(farbe, breite)} />
    </pattern>
  );
}

function Lageplan({ modus, typ, lage, onLage, onDrehen, verletzt, vorschauTyp, terrasse, fokusRegel }) {
  const svgRef = useRef(null);
  const zug = useRef(null);
  const regeln = modus !== "parzelle";
  const animiert = modus === "regelwerk";
  const interaktiv = modus === "implantation";
  const zeigeHaus = typ && ["typ", "implantation", "uebersicht"].includes(modus);
  const m = zeigeHaus ? planMass(typ, lage.gedreht) : null;
  const zeigeMasse = zeigeHaus && (modus === "implantation" || modus === "uebersicht");
  const a = zeigeHaus ? abstaende(lage, typ) : null;
  const bx2 = BAUFELD.x + BAUFELD.b, by2 = BAUFELD.y + BAUFELD.t;

  const punkt = (e) => {
    const svg = svgRef.current;
    const p = svg.createSVGPoint();
    p.x = e.clientX; p.y = e.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  };
  const runden = (v) => Math.round(v / RASTER_M) * RASTER_M;

  const haltung = {
    onPointerDown: (e) => {
      if (!interaktiv) return;
      const q = punkt(e);
      zug.current = { dx: q.x - lage.x, dy: q.y - lage.y };
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    onPointerMove: (e) => {
      if (!zug.current) return;
      const q = punkt(e);
      onLage({ ...lage, x: runden(q.x - zug.current.dx), y: runden(q.y - zug.current.dy) }, "ziehen");
    },
    onPointerUp: () => { zug.current = null; },
    onPointerCancel: () => { zug.current = null; },
    onKeyDown: (e) => {
      if (!interaktiv) return;
      const s = e.shiftKey ? 1 : 0.5;
      const d = { ArrowLeft: [-s, 0], ArrowRight: [s, 0], ArrowUp: [0, -s], ArrowDown: [0, s] }[e.key];
      if (d) { e.preventDefault(); onLage({ ...lage, x: lage.x + d[0], y: lage.y + d[1] }, "taste"); }
      if (e.key === "r" || e.key === "R") { e.preventDefault(); onDrehen(); }
    },
  };

  const regelLinie = (id, x1, y1, x2, y2) => {
    const rot = verletzt === id || fokusRegel === id;
    return (
      <line key={id} x1={x1} y1={y1} x2={x2} y2={y2}
        style={strich(rot ? "var(--alert)" : "var(--accent)", rot ? 0.16 : 0.05, { strokeDasharray: rot ? "none" : "0.45 0.3", opacity: rot ? 1 : 0.75 })} />
    );
  };

  const vorschau = vorschauTyp ? planMass(vorschauTyp, false) : null;
  const vx = vorschau ? (PARZ_B - vorschau.b) / 2 : 0;

  return (
    <svg ref={svgRef} viewBox="-13 -10 46 49" className="w-full h-auto block select-none" role="img"
      aria-label={`Lageplan der Parzelle ${PARZELLE.kennung}${regeln ? " mit bebaubarer Fläche" : ""}`}>
      <defs>
        <Schraffur id="h-nachbar" farbe="var(--hatch)" abstand={0.6} breite={0.05} />
        <Schraffur id="h-bau" farbe="var(--accent)" abstand={0.9} breite={0.045} />
        <Schraffur id="h-alert" farbe="var(--alert)" abstand={0.5} breite={0.08} />
      </defs>

      {/* Straße */}
      <rect x="-13" y="-9" width="46" height="7.2" style={{ fill: "var(--street)" }} />
      <line x1="-13" y1="-1.8" x2="33" y2="-1.8" style={strich("var(--line-strong)", 0.06)} />
      <text x="10" y="-5" textAnchor="middle" style={txt("var(--mute)", 0.8, { letterSpacing: 0.35 })}>RUE DES TILLEULS · STRASSENSEITE NORDEN</text>

      {/* Nachbarparzellen */}
      <g style={strich("var(--line-strong)", 0.05)}>
        <line x1="-13" y1="0" x2="0" y2="0" /><line x1="20" y1="0" x2="33" y2="0" />
        <line x1="-13" y1={PARZ_T} x2="33" y2={PARZ_T} />
        <line x1="0" y1={PARZ_T} x2="0" y2="39" /><line x1="20" y1={PARZ_T} x2="20" y2="39" />
      </g>
      <rect x="-11.8" y="6" width="6.3" height="11" style={{ fill: "url(#h-nachbar)", stroke: "var(--hatch)", strokeWidth: 0.06 }} />
      <rect x="23.4" y="5" width="7" height="10" style={{ fill: "url(#h-nachbar)", stroke: "var(--hatch)", strokeWidth: 0.06 }} />
      <text x="-8.65" y="19" textAnchor="middle" style={txt("var(--faint)", 0.62)}>WESTEN · BEBAUT</text>
      <text x="26.9" y="17" textAnchor="middle" style={txt("var(--faint)", 0.62)}>OSTEN · BEBAUT</text>

      {/* Parzelle */}
      <rect x="0" y="0" width={PARZ_B} height={PARZ_T} style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: 0.16 }} />
      <text x="0.7" y={PARZ_T - 0.8} style={txt("var(--ink)", 0.7, { fontWeight: 500 })}>{PARZELLE.kennung} · {zahl(PARZELLE.flaeche_m2)} m²</text>

      {/* Regelwerk: Abstandslinien und bebaubare Fläche */}
      {regeln && (
        <g key={animiert ? "anim" : "ruhig"}>
          <rect x={BAUFELD.x} y={BAUFELD.y} width={BAUFELD.b} height={BAUFELD.t}
            className={animiert ? "anim-flaeche" : ""} style={{ fill: "var(--accent-tint)" }} />
          <rect x={BAUFELD.x} y={BAUFELD.y} width={BAUFELD.b} height={BAUFELD.t}
            className={animiert ? "anim-flaeche" : ""} style={{ fill: "url(#h-bau)", opacity: zeigeHaus ? 0.35 : 0.6 }} />
          <g className={animiert ? "anim-flaeche" : ""}>
            {regelLinie("strasse", 0, BAUFELD.y, PARZ_B, BAUFELD.y)}
            {regelLinie("hinten", 0, by2, PARZ_B, by2)}
            {regelLinie("west", BAUFELD.x, 0, BAUFELD.x, PARZ_T)}
            {regelLinie("ost", bx2, 0, bx2, PARZ_T)}
          </g>
          <path d={`M${BAUFELD.x} ${BAUFELD.y}H${bx2}V${by2}H${BAUFELD.x}Z`} pathLength="1"
            className={animiert ? "anim-linie" : ""} style={strich("var(--accent)", 0.17, { strokeLinejoin: "miter" })} />
          {!zeigeHaus && !vorschau ? (
            <g className={animiert ? "anim-text" : ""} textAnchor="middle">
              <text x="10" y="13.6" style={txt("var(--accent)", 0.7, { letterSpacing: 0.18 })}>BEBAUBARE FLÄCHE</text>
              <text x="10" y="16" style={{ fill: "var(--accent)", fontFamily: "Archivo, Arial, sans-serif", fontSize: 2, fontWeight: 600, fontStretch: "116%" }}>
                {zahl(BAUFELD.b, 1)} × {zahl(BAUFELD.t, 1)} m
              </text>
              <text x="10" y="17.6" style={txt("var(--accent)", 0.62)}>max. Grundfläche {zahl(REGELWERK.max_grundflaeche_m2, 1)} m² (GFZ {REGELWERK.grundflaechenzahl_prozent} %)</text>
            </g>
          ) : (
            <text x={BAUFELD.x + 0.1} y={BAUFELD.y - 0.55} style={txt("var(--accent)", 0.6, { letterSpacing: 0.1, ...freistellen })}>
              BEBAUBARE FLÄCHE {zahl(BAUFELD.b, 1)} × {zahl(BAUFELD.t, 1)} m
            </text>
          )}
          {!zeigeMasse && (
            <g className={animiert ? "anim-text" : ""}>
              <MassV y1={0} y2={BAUFELD.y} x={-1.6} label={zahl(REGELWERK.abstand_strasse_m, 2)} farbe="var(--accent)" />
              <MassV y1={BAUFELD.y} y2={by2} x={-1.6} label={zahl(BAUFELD.t, 2)} farbe="var(--accent)" />
              <MassV y1={by2} y2={PARZ_T} x={-1.6} label={zahl(REGELWERK.abstand_hinten_m, 2)} farbe="var(--accent)" />
              <MassH x1={0} x2={BAUFELD.x} y={33.4} label={zahl(REGELWERK.abstand_seitlich_m, 2)} farbe="var(--accent)" />
              <MassH x1={BAUFELD.x} x2={bx2} y={33.4} label={zahl(BAUFELD.b, 2)} farbe="var(--accent)" />
              <MassH x1={bx2} x2={PARZ_B} y={33.4} label={zahl(REGELWERK.abstand_seitlich_m, 2)} farbe="var(--accent)" />
            </g>
          )}
        </g>
      )}

      {/* Gesamtmaße Parzelle */}
      <MassV y1={0} y2={PARZ_T} x={-3.8} label={zahl(PARZ_T, 2)} von={0} farbe="var(--ink)" />
      <MassH x1={0} x2={PARZ_B} y={35.6} label={zahl(PARZ_B, 2)} von={PARZ_T} farbe="var(--ink)" />
      <text x="10" y="38.4" textAnchor="middle" style={txt("var(--mute)", 0.62, { letterSpacing: 0.25 })}>GARTENSEITE SÜDEN</text>

      {/* Vorschau gesperrter Typ */}
      {vorschau && (
        <g>
          <rect x={vx} y={BAUFELD.y} width={vorschau.b} height={vorschau.t} style={{ fill: "var(--alert-tint)", stroke: "var(--alert)", strokeWidth: 0.1, strokeDasharray: "0.5 0.3" }} />
          <rect x={vx} y={BAUFELD.y} width={BAUFELD.x - vx} height={vorschau.t} style={{ fill: "url(#h-alert)" }} />
          <rect x={bx2} y={BAUFELD.y} width={vx + vorschau.b - bx2} height={vorschau.t} style={{ fill: "url(#h-alert)" }} />
          <text x="10" y={BAUFELD.y + 4.3} textAnchor="middle" style={txt("var(--alert)", 0.72, { fontWeight: 500 })}>{vorschauTyp.name} · Flachdach</text>
          <MassH x1={vx} x2={vx + vorschau.b} y={BAUFELD.y + vorschau.t + 1.3} label={`${zahl(vorschau.b, 2)} > ${zahl(BAUFELD.b, 2)}`} farbe="var(--alert)" />
        </g>
      )}

      {/* Baukörper */}
      {zeigeHaus && (
        <g>
          {terrasse && (
            <rect x={lage.x + (m.b - TERRASSE_MASS[0]) / 2} y={lage.y + m.t} width={TERRASSE_MASS[0]} height={TERRASSE_MASS[1]}
              style={{ fill: "none", stroke: "var(--mute)", strokeWidth: 0.07, strokeDasharray: "0.3 0.2" }} />
          )}
          {terrasse && (
            <text x={lage.x + m.b / 2} y={lage.y + m.t + 1.85} textAnchor="middle" style={txt("var(--mute)", 0.6)}>Terrasse 24 m²</text>
          )}
          <g {...haltung} tabIndex={interaktiv ? 0 : undefined} role={interaktiv ? "button" : undefined}
            aria-label={interaktiv ? `Baukörper ${typ.name}. Pfeiltasten verschieben, R dreht um 90 Grad.` : undefined}
            className={interaktiv ? "greifbar" : ""}>
            <rect x={lage.x} y={lage.y} width={m.b} height={m.t}
              style={{ fill: "var(--house)", stroke: interaktiv ? "var(--accent)" : "var(--ink)", strokeWidth: interaktiv ? 0.14 : 0.1 }} />
            {lage.gedreht ? (
              <line x1={lage.x + m.b / 2} y1={lage.y} x2={lage.x + m.b / 2} y2={lage.y + m.t} style={strich("var(--sheet)", 0.07, { strokeDasharray: "0.6 0.3" })} />
            ) : (
              <line x1={lage.x} y1={lage.y + m.t / 2} x2={lage.x + m.b} y2={lage.y + m.t / 2} style={strich("var(--sheet)", 0.07, { strokeDasharray: "0.6 0.3" })} />
            )}
            <text x={lage.x + m.b / 2} y={lage.y + m.t / 2 - 0.45} textAnchor="middle"
              style={txt("var(--sheet)", 0.72, { fontWeight: 500 })}
              transform={lage.gedreht ? `rotate(-90 ${lage.x + m.b / 2} ${lage.y + m.t / 2})` : undefined}>
              {zahl(typ.grundflaeche_m2)} m²
            </text>
          </g>
          {zeigeMasse && (
            <g>
              <MassV y1={0} y2={lage.y} x={lage.x + 1.4} label={zahl(a.strasse, 2)} farbe="var(--ink)" gr={0.66} />
              <MassV y1={lage.y + m.t} y2={PARZ_T} x={lage.x + 1.4} label={zahl(a.hinten, 2)} farbe="var(--ink)" gr={0.66} />
              <MassH x1={0} x2={lage.x} y={lage.y + m.t - 1.2} label={zahl(a.west, 2)} farbe="var(--ink)" gr={0.66} />
              <MassH x1={lage.x + m.b} x2={PARZ_B} y={lage.y + m.t - 1.2} label={zahl(a.ost, 2)} farbe="var(--ink)" gr={0.66} />
            </g>
          )}
        </g>
      )}

      {/* Nordpfeil und Maßstabsleiste */}
      <g transform="translate(28.2 33.6)">
        <circle r="1.5" style={strich("var(--ink)", 0.06)} />
        <path d="M0 -1.5 L0.55 0.9 L0 0.45 L-0.55 0.9 Z" style={{ fill: "var(--ink)" }} />
        <text y="-2" textAnchor="middle" style={txt("var(--ink)", 0.8, { fontWeight: 500 })}>N</text>
      </g>
      <g transform="translate(-12 35.6)">
        <rect x="0" y="0" width="5" height="0.45" style={{ fill: "var(--ink)" }} />
        <rect x="5" y="0" width="5" height="0.45" style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: 0.05 }} />
        <text x="0" y="1.5" style={txt("var(--mute)", 0.6)}>0</text>
        <text x="5" y="1.5" textAnchor="middle" style={txt("var(--mute)", 0.6)}>5</text>
        <text x="10" y="1.5" textAnchor="end" style={txt("var(--mute)", 0.6)}>10 m</text>
      </g>
    </svg>
  );
}

// Axonometrie (isometrisch, Blick von Südosten). X = Osten, Y = Süden, Z = oben.
// kompakt: Vorschau für die Typkarten — alle Typen im gleichen Maßstab, mit Höhenmaß.
function Axonometrie({ typ, linieId, optionen, kompakt = false }) {
  const mat = materialien(linieId, optionen);
  const [w, d] = typ.abmessung_m;
  const R = typ.firsthoehe_m;
  const flach = /Flachdach/.test(typ.dach);
  const neigung = parseFloat((typ.dach.match(/(\d+)°/) || [0, 0])[1]);
  const E = typ.traufhoehe_m ?? (flach ? R : R - (d / 2) * Math.tan((neigung * Math.PI) / 180));
  // Plateau: eingeschossiger Hauptkörper mit Attika, Teilobergeschoss auf der Westseite (schematisch)
  const teilOG = flach && /Teilobergeschoss/.test(typ.kubatur);
  const W = teilOG ? 3.4 : E;
  const ogB = teilOG ? Math.round(w * 0.8) / 2 : 0;
  const C = Math.cos(Math.PI / 6);
  const P = (X, Y, Z) => [(X - Y) * C, (X + Y) * 0.5 - Z];
  const pts = (arr) => arr.map((p) => P(...p).map((v) => v.toFixed(3)).join(",")).join(" ");
  const L = (p1, p2, style, key) => {
    const [x1, y1] = P(...p1); const [x2, y2] = P(...p2);
    return <line key={key} x1={x1} y1={y1} x2={x2} y2={y2} style={style} />;
  };
  const kante = { stroke: "var(--axo)", strokeWidth: kompakt ? 0.1 : 0.07, strokeLinejoin: "round" };
  const zOben = (v) => (flach ? W : E + (R - E) * (1 - Math.abs(v - d / 2) / (d / 2)));
  const cp = { x0: w + 1.2, x1: w + 7.2, y0: 0, y1: 5.6, h: 2.6 };
  const mitCarport = mat.carport && !kompakt;
  const mitKeller = mat.keller && !kompakt;

  const rahmen = (breite, hoehe, carport) => {
    const rx = carport ? breite + 9 : breite + (kompakt ? 1.2 : 3.5);
    const r0 = kompakt ? -1.2 : -3, ry0 = kompakt ? -1.2 : -2, ry1 = d + (kompakt ? 3.3 : 5.5);
    const huelle = [[r0, ry0, 0], [rx, ry0, 0], [rx, ry1, 0], [r0, ry1, 0], [0, 0, hoehe], [0, d / 2, hoehe],
      ...(kompakt ? [[-4.4, d, hoehe / 2]] : [[0, d, -3]])].map((p) => P(...p));
    const xs = huelle.map((p) => p[0]), ys = huelle.map((p) => p[1]);
    const rand = kompakt ? 0.4 : 1;
    return { rx, r0, ry0, ry1, minX: Math.min(...xs) - rand, maxX: Math.max(...xs) + rand, minY: Math.min(...ys) - rand, maxY: Math.max(...ys) + rand };
  };
  const g = rahmen(w, R, mitCarport);
  let vb = [g.minX, g.minY, g.maxX - g.minX, g.maxY - g.minY];
  if (kompakt) {
    const ref = rahmen(MAX_TYPBREITE, REGELWERK.max_firsthoehe_m, false);
    const bw = ref.maxX - ref.minX, bh = ref.maxY - ref.minY;
    vb = [(g.minX + g.maxX) / 2 - bw / 2, g.maxY - bh, bw, bh];
  }

  const sued = mat.fassadeSued, ost = mat.fassade;
  const holzLinien = (seite) => {
    const out = [];
    const fm = seite === "sued" ? sued : ost;
    if (fm.textur !== "holz") return out;
    const len = seite === "sued" ? w : d;
    for (let u = 0.38; u < len - 0.1; u += 0.38) {
      out.push(seite === "sued"
        ? L([u, d, 0], [u, d, W], strich(fm.linie, 0.035), `hs${u}`)
        : L([w, u, 0], [w, u, zOben(u)], strich(fm.linie, 0.035), `ho${u}`));
    }
    return out;
  };
  const zEG = 2.9;
  const fensterSued = [];
  const nEG = mat.bodentief ? Math.max(2, Math.floor(w / 4)) : Math.floor(w / 2.8);
  for (let i = 0; i < nEG; i++) {
    const c = (w * (i + 0.5)) / nEG, br = mat.bodentief ? 2.3 : 1.25;
    const z0 = mat.bodentief ? 0.05 : 0.95, z1 = mat.bodentief ? 2.4 : 2.25;
    fensterSued.push(
      <g key={`fe${i}`}>
        <polygon points={pts([[c - br / 2, d, z0], [c + br / 2, d, z0], [c + br / 2, d, z1], [c - br / 2, d, z1]])} style={{ fill: MATERIAL.glas.farbe, stroke: mat.rahmen, strokeWidth: 0.12 }} />
        {mat.bodentief && L([c, d, z0], [c, d, z1], strich(mat.rahmen, 0.1))}
      </g>
    );
  }
  if (W > 4.4) {
    const nOG = Math.floor(w / 3);
    for (let i = 0; i < nOG; i++) {
      const c = (w * (i + 0.5)) / nOG, z1 = Math.min(4.95, W - 0.4);
      fensterSued.push(<polygon key={`fo${i}`} points={pts([[c - 0.55, d, 3.7], [c + 0.55, d, 3.7], [c + 0.55, d, z1], [c - 0.55, d, z1]])} style={{ fill: MATERIAL.glas.farbe, stroke: mat.rahmen, strokeWidth: 0.12 }} />);
    }
  }
  const fensterOst = [[d * 0.28, 1.0, 0.95, 2.25], ...(W > 4.4 ? [[d / 2, 0.9, 3.7, Math.min(4.9, W - 0.4)]] : []), ...(!flach && R - E > 2.5 ? [[d / 2, 0.55, E + 0.55, E + 1.35]] : [])]
    .map(([v, br, z0, z1], i) => (
      <polygon key={`fost${i}`} points={pts([[w, v - br / 2, z0], [w, v + br / 2, z0], [w, v + br / 2, z1], [w, v - br / 2, z1]])} style={{ fill: MATERIAL.glas.farbe, stroke: mat.rahmen, strokeWidth: 0.11 }} />
    ));

  const dachLinien = [];
  if (!flach) for (let k = 1; k < 9; k++) {
    const f = k / 9;
    dachLinien.push(L([0, d - (f * d) / 2, E + f * (R - E)], [w, d - (f * d) / 2, E + f * (R - E)], strich(mat.dach.linie, 0.05), `dl${k}`));
  }
  const pvPunkt = (u, f) => [u, d - (f * d) / 2, E + f * (R - E)];
  const pv = [];
  if (mat.pv && !flach) {
    const u1 = w * 0.16, u2 = w * 0.84, f1 = 0.12, f2 = 0.7;
    pv.push(<polygon key="pv" points={pts([pvPunkt(u1, f1), pvPunkt(u2, f1), pvPunkt(u2, f2), pvPunkt(u1, f2)])} style={{ fill: MATERIAL.pv.farbe, stroke: "var(--axo)", strokeWidth: 0.06 }} />);
    const sp = Math.round((u2 - u1) / 1.05);
    for (let i = 1; i < sp; i++) { const u = u1 + ((u2 - u1) * i) / sp; pv.push(L(pvPunkt(u, f1), pvPunkt(u, f2), strich(MATERIAL.pv.linie, 0.04), `pvs${i}`)); }
    for (let j = 1; j < 3; j++) { const f = f1 + ((f2 - f1) * j) / 3; pv.push(L(pvPunkt(u1, f), pvPunkt(u2, f), strich(MATERIAL.pv.linie, 0.04), `pvz${j}`)); }
  }

  return (
    <svg viewBox={vb.join(" ")} className="w-full h-auto block" role="img"
      aria-label={`Axonometrie ${typ.name}: ${flach ? "Flachdach" : typ.dach}, Firsthöhe ${meter(R)}, Fassade ${sued.name}`}>
      <polygon points={pts([[g.r0, g.ry0, 0], [g.rx, g.ry0, 0], [g.rx, g.ry1, 0], [g.r0, g.ry1, 0]])} style={{ fill: "var(--street)", stroke: "var(--line-strong)", strokeWidth: 0.05 }} />
      {!kompakt && (() => { const [x, y] = P(w / 2 - 1, g.ry1, 0); return <text x={x} y={y + 1.1} textAnchor="middle" style={txt("var(--mute)", 0.62, { letterSpacing: 0.2 })}>SÜDEN · GARTEN</text>; })()}

      {kompakt && (() => {
        const xm = -1.3;
        const oben = flach ? [0, d, R] : [0, d / 2, R];
        const [lx, ly] = P(xm, d, R / 2);
        const t = 0.35;
        const [ax, ay] = P(xm, d, 0), [bx, by] = P(xm, d, R);
        return (
          <g>
            {L([0, d, 0], [xm - 0.4, d, 0], strich("var(--mute)", 0.05))}
            {L(oben, [xm - 0.4, d, R], strich("var(--mute)", 0.05, { strokeDasharray: "0.3 0.2" }))}
            <line x1={ax} y1={ay} x2={bx} y2={by} style={strich("var(--mute)", 0.07)} />
            <line x1={ax - t} y1={ay + t} x2={ax + t} y2={ay - t} style={strich("var(--mute)", 0.12)} />
            <line x1={bx - t} y1={by + t} x2={bx + t} y2={by - t} style={strich("var(--mute)", 0.12)} />
            <text x={lx - 0.5} y={ly + 0.5} textAnchor="end" style={txt("var(--ink)", 1.45)}>{zahl(R, 1)}</text>
          </g>
        );
      })()}

      {mat.terrasse && (
        <g>
          <polygon points={pts([[(w - 8) / 2, d, 0], [(w + 8) / 2, d, 0], [(w + 8) / 2, d + 3, 0], [(w - 8) / 2, d + 3, 0]])} style={{ fill: MATERIAL.terrasse.farbe, stroke: "var(--axo)", strokeWidth: 0.05 }} />
          {[0.5, 1, 1.5, 2, 2.5].map((o) => L([(w - 8) / 2, d + o, 0], [(w + 8) / 2, d + o, 0], strich(MATERIAL.terrasse.linie, 0.035), `t${o}`))}
        </g>
      )}

      {!flach && <polygon points={pts([[0, 0, E], [w, 0, E], [w, d / 2, R], [0, d / 2, R]])} style={{ fill: mat.dach.linie, ...kante }} />}

      {/* Südfassade */}
      <polygon points={pts([[0, d, 0], [w, d, 0], [w, d, W], [0, d, W]])} style={{ fill: sued.farbe, ...kante }} />
      {holzLinien("sued")}
      {mat.ziegelEG && (
        <g>
          <polygon points={pts([[0, d, 0], [w, d, 0], [w, d, zEG], [0, d, zEG]])} style={{ fill: MATERIAL.ziegel.farbe }} />
          {[0.36, 0.72, 1.08, 1.44, 1.8, 2.16, 2.52].map((z) => L([0, d, z], [w, d, z], strich(MATERIAL.ziegel.linie, 0.03), `zs${z}`))}
        </g>
      )}
      {fensterSued}

      {/* Ostgiebel */}
      <polygon points={pts(flach ? [[w, 0, 0], [w, d, 0], [w, d, W], [w, 0, W]] : [[w, 0, 0], [w, d, 0], [w, d, E], [w, d / 2, R], [w, 0, E]])} style={{ fill: ost.farbe, ...kante }} />
      {holzLinien("ost")}
      {mat.ziegelEG && (
        <g>
          <polygon points={pts([[w, 0, 0], [w, d, 0], [w, d, zEG], [w, 0, zEG]])} style={{ fill: MATERIAL.ziegel.farbe }} />
          {[0.36, 0.72, 1.08, 1.44, 1.8, 2.16, 2.52].map((z) => L([w, 0, z], [w, d, z], strich(MATERIAL.ziegel.linie, 0.03), `zo${z}`))}
        </g>
      )}
      {fensterOst}
      <polygon points={pts(flach ? [[w, 0, 0], [w, d, 0], [w, d, W], [w, 0, W]] : [[w, 0, 0], [w, d, 0], [w, d, E], [w, d / 2, R], [w, 0, E]])} style={{ fill: "#000", fillOpacity: 0.07, ...kante }} />

      {/* Dach */}
      {flach ? (
        <g>
          <polygon points={pts([[0, 0, W], [w, 0, W], [w, d, W], [0, d, W]])} style={{ fill: "#8E928F", ...kante }} />
          <polygon points={pts([[0.35, 0.35, W], [w - 0.35, 0.35, W], [w - 0.35, d - 0.35, W], [0.35, d - 0.35, W]])} style={{ fill: "#7C807D" }} />
          {teilOG && (
            <g>
              <polygon points={pts([[0, d, W], [ogB, d, W], [ogB, d, R], [0, d, R]])} style={{ fill: sued.farbe, ...kante }} />
              {sued.textur === "holz" && Array.from({ length: Math.floor(ogB / 0.38) }, (_, i) => L([0.38 * (i + 1), d, W], [0.38 * (i + 1), d, R], strich(sued.linie, 0.035), `ogh${i}`))}
              {[0.25, 0.75].map((f) => (
                <polygon key={`ogf${f}`} points={pts([[ogB * f - 0.6, d, W + 0.9], [ogB * f + 0.6, d, W + 0.9], [ogB * f + 0.6, d, R - 0.8], [ogB * f - 0.6, d, R - 0.8]])} style={{ fill: MATERIAL.glas.farbe, stroke: mat.rahmen, strokeWidth: 0.12 }} />
              ))}
              <polygon points={pts([[ogB, 0, W], [ogB, d, W], [ogB, d, R], [ogB, 0, R]])} style={{ fill: ost.farbe, ...kante }} />
              {ost.textur === "holz" && Array.from({ length: Math.floor(d / 0.38) }, (_, i) => L([ogB, 0.38 * (i + 1), W], [ogB, 0.38 * (i + 1), R], strich(ost.linie, 0.035), `ogo${i}`))}
              <polygon points={pts([[ogB, d * 0.35, W + 0.9], [ogB, d * 0.6, W + 0.9], [ogB, d * 0.6, R - 0.8], [ogB, d * 0.35, R - 0.8]])} style={{ fill: MATERIAL.glas.farbe, stroke: mat.rahmen, strokeWidth: 0.11 }} />
              <polygon points={pts([[ogB, 0, W], [ogB, d, W], [ogB, d, R], [ogB, 0, R]])} style={{ fill: "#000", fillOpacity: 0.07, ...kante }} />
              <polygon points={pts([[0, 0, R], [ogB, 0, R], [ogB, d, R], [0, d, R]])} style={{ fill: "#8E928F", ...kante }} />
              <polygon points={pts([[0.35, 0.35, R], [ogB - 0.35, 0.35, R], [ogB - 0.35, d - 0.35, R], [0.35, d - 0.35, R]])} style={{ fill: "#7C807D" }} />
            </g>
          )}
        </g>
      ) : (
        <g>
          <polygon points={pts([[0, d, E], [w, d, E], [w, d / 2, R], [0, d / 2, R]])} style={{ fill: mat.dach.farbe, ...kante }} />
          {dachLinien}
          {pv}
          <polygon points={pts([[0, d, E], [w, d, E], [w, d / 2, R], [0, d / 2, R]])} style={{ fill: "none", ...kante }} />
        </g>
      )}

      {mitCarport && (
        <g>
          {[[cp.x0, cp.y1], [cp.x1, cp.y1], [cp.x1, cp.y0]].map(([x, y], i) => L([x, y, 0], [x, y, cp.h], strich("#6C716E", 0.14), `cpp${i}`))}
          <polygon points={pts([[cp.x0, cp.y1, cp.h], [cp.x1, cp.y1, cp.h], [cp.x1, cp.y1, cp.h + 0.25], [cp.x0, cp.y1, cp.h + 0.25]])} style={{ fill: "#B9BDB9", ...kante }} />
          <polygon points={pts([[cp.x1, cp.y0, cp.h], [cp.x1, cp.y1, cp.h], [cp.x1, cp.y1, cp.h + 0.25], [cp.x1, cp.y0, cp.h + 0.25]])} style={{ fill: "#A3A7A3", ...kante }} />
          <polygon points={pts([[cp.x0, cp.y0, cp.h + 0.25], [cp.x1, cp.y0, cp.h + 0.25], [cp.x1, cp.y1, cp.h + 0.25], [cp.x0, cp.y1, cp.h + 0.25]])} style={{ fill: "#D6D9D5", ...kante }} />
        </g>
      )}

      {mitKeller && (
        <g style={strich("var(--mute)", 0.07, { strokeDasharray: "0.35 0.25" })}>
          {L([0, d, 0], [0, d, -2.6])}{L([w / 2, d, 0], [w / 2, d, -2.6])}{L([w / 2, 0, 0], [w / 2, 0, -2.6])}
          {L([0, d, -2.6], [w / 2, d, -2.6])}{L([w / 2, d, -2.6], [w / 2, 0, -2.6])}
          {(() => { const [x, y] = P(w / 4, d, -2.6); return <text x={x} y={y + 1} textAnchor="middle" style={txt("var(--mute)", 0.62, { strokeWidth: 0, strokeDasharray: "none" })}>KELLER</text>; })()}
        </g>
      )}
    </svg>
  );
}

function MaterialLegende({ linieId, optionen }) {
  const mat = materialien(linieId, optionen);
  const posten = [
    { k: "Fassade", n: mat.fassade.name, f: mat.fassade.farbe },
    ...(mat.fassadeSued !== mat.fassade ? [{ k: "Südfassade", n: mat.fassadeSued.name, f: mat.fassadeSued.farbe }] : []),
    ...(mat.ziegelEG ? [{ k: "Erdgeschoss", n: MATERIAL.ziegel.name, f: MATERIAL.ziegel.farbe }] : []),
    { k: "Dach", n: mat.dach.name, f: mat.dach.farbe },
    { k: "Fenster", n: `${mat.fensterName}${mat.bodentief && linieId !== "signature" ? ", Süd bodentief" : ""}`, f: MATERIAL.glas.farbe },
    ...(mat.pv ? [{ k: "Dachfläche Süd", n: "Photovoltaik 6 kWp", f: MATERIAL.pv.farbe }] : []),
  ];
  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 px-4 py-3 border-t bd">
      {posten.map((p) => (
        <div key={p.k} className="flex items-center gap-3 min-w-0">
          <span className="w-5 h-5 border bd-strong flex-none" style={{ background: p.f }} aria-hidden="true" />
          <div className="min-w-0 leading-tight">
            <dt className="eyebrow">{p.k}</dt>
            <dd className="text-sm t-ink">{p.n}</dd>
          </div>
        </div>
      ))}
    </dl>
  );
}

function TypSkizze({ typ, klasse = "w-16" }) {
  const m = planMass(typ, false);
  const x = (PARZ_B - m.b) / 2;
  const bx2 = BAUFELD.x + BAUFELD.b;
  const ueber = m.b > BAUFELD.b;
  return (
    <svg viewBox="-1.5 -1.5 23 34" className={`${klasse} h-auto block flex-none`} aria-hidden="true">
      <defs><Schraffur id={`hs-${typ.id}`} farbe="var(--alert)" abstand={0.6} breite={0.12} /></defs>
      <rect x="0" y="0" width={PARZ_B} height={PARZ_T} style={{ fill: "var(--sheet)", stroke: "var(--line-strong)", strokeWidth: 0.25 }} />
      <rect x={BAUFELD.x} y={BAUFELD.y} width={BAUFELD.b} height={BAUFELD.t} style={{ fill: "var(--accent-tint)", stroke: "var(--accent)", strokeWidth: 0.3 }} />
      <rect x={x} y={BAUFELD.y} width={m.b} height={m.t} style={{ fill: ueber ? "var(--alert-tint)" : "var(--house)", stroke: ueber ? "var(--alert)" : "none", strokeWidth: 0.3 }} />
      {ueber && <rect x={x} y={BAUFELD.y} width={BAUFELD.x - x} height={m.t} style={{ fill: `url(#hs-${typ.id})` }} />}
      {ueber && <rect x={bx2} y={BAUFELD.y} width={x + m.b - bx2} height={m.t} style={{ fill: `url(#hs-${typ.id})` }} />}
    </svg>
  );
}

function SchichtenSkizze() {
  const zeile = (y, x0, titel, sub, farbe) => (
    <g>
      <line x1={x0} y1={y} x2="25" y2={y} style={strich("var(--mute)", 0.06)} />
      <circle cx={x0} cy={y} r="0.22" style={{ fill: "var(--ink)" }} />
      <text x="25.8" y={y - 0.25} style={txt(farbe, 1.05, { fontWeight: 500 })}>{titel}</text>
      <text x="25.8" y={y + 1.25} style={txt("var(--mute)", 0.82)}>{sub}</text>
    </g>
  );
  return (
    <svg viewBox="-1 -2 52 35" className="w-full h-auto block" role="img" aria-label="Drei Ebenen: Parzelle, bebaubare Fläche, Ihr Entwurf">
      <defs><Schraffur id="h-schicht" farbe="var(--accent)" abstand={0.9} breite={0.05} /></defs>
      <rect x="0" y="0" width="20" height="31" style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: 0.16 }} />
      <rect x="3" y="5" width="14" height="21" style={{ fill: "url(#h-schicht)", stroke: "var(--accent)", strokeWidth: 0.16 }} />
      <rect x="4" y="5" width="12" height="8" style={{ fill: "var(--house)" }} />
      {zeile(1.6, 19, "Parzelle", "Kataster, 612 m²", "var(--ink)")}
      {zeile(20, 16.5, "Bebaubare Fläche", "aus dem PLU, harte Grenze", "var(--accent)")}
      {zeile(9, 15.5, "Ihr Entwurf", "Typ, Linie, Optionen, Lage", "var(--ink)")}
    </svg>
  );
}

function Planblatt({ inhalt, blatt, children, fuss, overlay, massstab = "schematisch" }) {
  const stand = useMemo(() => new Date().toLocaleDateString("de-DE"), []);
  return (
    <figure className="border bd-strong bg-sheet relative m-0">
      <div className="flex items-center justify-between gap-4 px-4 py-2 border-b bd">
        <span className="eyebrow">{inhalt}</span>
        <span className="eyebrow">Maßstab {massstab}</span>
      </div>
      <div className="relative px-3 py-3">
        {children}
        {overlay}
      </div>
      {fuss}
      <div className="grid grid-cols-2 md:grid-cols-4 border-t bd-strong">
        {[
          ["Projekt", "EFH · Vorentwurf"],
          ["Parzelle", `${PARZELLE.kennung} · Treillières`],
          ["Stand", stand],
          ["Blatt", `${blatt} / ${SCHRITTE.length}`],
        ].map(([k, v], i) => (
          <div key={k} className={`px-3 py-2 ${i > 0 ? "md:border-l" : ""} ${i % 2 === 1 ? "border-l" : ""} ${i > 1 ? "border-t md:border-t-0" : ""} bd`}>
            <div className="eyebrow">{k}</div>
            <div className="text-xs t-ink f-mono num">{v}</div>
          </div>
        ))}
      </div>
    </figure>
  );
}

/* ---------------------------------------------------------------------
   RAHMEN — Kopfzeile, Korridorbalken, kleine Bausteine
   --------------------------------------------------------------------- */

const himmelsrichtung = (s) => s.replace("ue", "ü");

function Kopf({ eyebrow, titel, children, gross }) {
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

function Kopfzeile({ schritt, maxSchritt, onGehe, gesendet }) {
  return (
    <header className="border-b bd bg-paper">
      <div className="max-w-7xl mx-auto px-6 lg:px-10 pt-4 flex flex-wrap items-end gap-x-10 gap-y-2">
        <div className="flex items-baseline gap-3 pb-3">
          <span className="f-display text-2xl font-semibold t-ink" style={{ fontStretch: "125%", letterSpacing: "-0.02em" }}>{MARKE}</span>
          <span className="eyebrow hidden sm:inline">Vorentwurf auf Ihrer Parzelle</span>
        </div>
        <nav aria-label="Schritte" className="flex-1 overflow-x-auto">
          <ol className="flex items-end lg:justify-end gap-1 min-w-max">
            {SCHRITTE.map((s) => {
              const erreichbar = s.nr <= maxSchritt && !gesendet;
              const aktuell = s.nr === schritt && !gesendet;
              return (
                <li key={s.nr}>
                  <button type="button" disabled={!erreichbar} onClick={() => onGehe(s.nr)} aria-current={aktuell ? "step" : undefined}
                    className={`px-2 pt-2 pb-3 text-xs flex items-baseline gap-1.5 border-b-2 ${aktuell ? "bd-accent t-ink font-medium" : `border-transparent ${erreichbar ? "t-mute" : "t-faint"}`}`}>
                    <span className="f-mono num">{s.nr}</span>
                    <span>{s.kurz}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
      </div>
    </header>
  );
}

const SKALA = [300000, 550000];

function Korridorskala({ lo, hi }) {
  const B = 240;
  const x = (v) => ((Math.min(Math.max(v, SKALA[0]), SKALA[1]) - SKALA[0]) / (SKALA[1] - SKALA[0])) * B;
  const ticks = [300000, 350000, 400000, 450000, 500000, 550000];
  return (
    <svg viewBox={`-6 0 ${B + 30} 34`} className="w-64 h-auto hidden md:block" aria-hidden="true">
      <line x1="0" y1="14" x2={B} y2="14" style={strich("var(--line-strong)", 1)} />
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} y1="10" x2={x(t)} y2="18" style={strich("var(--line-strong)", 1)} />
          <text x={x(t)} y="30" textAnchor="middle" style={txt("var(--faint)", 8.5)}>{t / 1000}</text>
        </g>
      ))}
      <text x={B + 8} y="30" style={txt("var(--faint)", 8.5)}>Tsd.</text>
      {lo != null && <rect x={x(lo)} y="8" width={Math.max(3, x(hi) - x(lo))} height="12" style={{ fill: "var(--accent)", transition: "all .35s ease" }} />}
    </svg>
  );
}

function Korridorbalken({ korridor, onZurueck, zurueckAktiv, weiter }) {
  const k = korridor;
  return (
    <div className="fixed bottom-0 inset-x-0 z-40 border-t bd-strong bg-sheet">
      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-3 flex flex-wrap items-center gap-x-8 gap-y-3">
        <div className="min-w-0">
          <div className="eyebrow">Kostenkorridor · Schätzung, unverbindlich</div>
          {k.leer ? (
            <div className="text-sm t-mute py-1">Entsteht, sobald das Regelwerk der Parzelle ausgewertet ist.</div>
          ) : (
            <div key={`${rund(k.lo)}-${rund(k.hi)}`} className="flash px-1 -mx-1">
              <span className="f-display text-2xl font-semibold t-ink num whitespace-nowrap">
                ca. {zahl(rund(k.lo))} – {zahl(rund(k.hi))}&nbsp;€
              </span>
            </div>
          )}
          {!k.leer && (
            <div className="text-xs t-mute flex flex-wrap gap-x-3 gap-y-0.5 num">
              {k.posten.map((p) => (
                <span key={p.label} className={p.warn ? "t-warn" : ""}>{p.label}{p.text ? ` ${p.text}` : ""}</span>
              ))}
            </div>
          )}
        </div>
        {!k.leer && <Korridorskala lo={k.lo} hi={k.hi} />}
        <div className="ml-auto flex items-center gap-3">
          {weiter && !weiter.aktiv && weiter.grund && <span className="text-xs t-mute hidden lg:inline max-w-xs text-right">{weiter.grund}</span>}
          {zurueckAktiv != null && (
            <button type="button" className="btn btn-ghost" onClick={onZurueck} disabled={!zurueckAktiv}>Zurück</button>
          )}
          {weiter && (
            <button type="button" className="btn btn-primary" onClick={weiter.aktion} disabled={!weiter.aktiv}>
              {weiter.label} <span aria-hidden="true">→</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Zeile({ k, v, betont }) {
  return (
    <div className="flex items-baseline justify-between gap-6 py-2 border-t bd">
      <dt className="text-sm t-mute">{k}</dt>
      <dd className={`text-sm text-right num ${betont || "t-ink"}`}>{v}</dd>
    </div>
  );
}

/* ---------------------------------------------------------------------
   SCHRITTE 1–5
   --------------------------------------------------------------------- */

function SchrittStart({ adresse, setAdresse, onSuchen }) {
  const [fehler, setFehler] = useState(false);
  const suchen = () => {
    if (!adresse.trim()) { setFehler(true); return; }
    setFehler(false);
    onSuchen();
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-start">
      <div className="lg:col-span-6 flex flex-col gap-10 lg:pt-6">
        <Kopf gross eyebrow="Vorentwurf statt Katalog" titel="Entwerfen Sie Ihr Haus innerhalb dessen, was Ihre Parzelle erlaubt.">
          <p>
            Emprise wertet die Bauvorschriften Ihrer Gemeinde, den PLU, für Ihr Grundstück aus. Diese Grenzen gelten ab dann
            für jede Entscheidung: Haustyp, Ausstattung und Lage auf der Parzelle. Den fertigen Vorentwurf prüft ein
            Architekturbüro und erstellt daraus ein verbindliches Angebot.
          </p>
        </Kopf>

        <div className="flex flex-col gap-2 max-w-xl">
          <label htmlFor="adresse" className="text-sm font-medium t-ink">Adresse des Grundstücks</label>
          <div className="flex flex-col sm:flex-row gap-2">
            <input id="adresse" className="field flex-1" value={adresse} aria-invalid={fehler}
              onChange={(e) => setAdresse(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") suchen(); }}
              placeholder="Straße, Postleitzahl, Ort" autoComplete="street-address" />
            <button type="button" className="btn btn-primary justify-center" onClick={suchen}>Parzelle suchen</button>
          </div>
          {fehler ? (
            <p className="text-sm t-alert">Bitte eine Adresse eingeben, mit Straße, Postleitzahl und Ort.</p>
          ) : (
            <p className="text-xs t-faint">Für die Vorführung ist eine Beispieladresse eingetragen.</p>
          )}
        </div>

        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-xl border-t bd pt-6">
          {[
            ["Kein Shop", "Hier wird nichts gekauft und nichts unterschrieben."],
            ["Keine Festpreise", "Alle Beträge sind Schätzspannen mit „ca.“."],
            ["Echte Prüfung", "Ein Architekturbüro sieht jeden Vorentwurf durch."],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="text-sm font-medium t-ink">{k}</dt>
              <dd className="text-sm t-mute mt-1">{v}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="lg:col-span-6">
        <Planblatt inhalt="Prinzip · drei Ebenen" blatt={1}
          fuss={
            <ol className="border-t bd">
              {[
                ["Parzelle und Regelwerk", "Automatisch aus Kataster und PLU ermittelt."],
                ["Ihr Vorentwurf", "Haustyp, Ausstattungslinie, Optionen, Lage auf dem Grundstück."],
                ["Prüfung durch das Architekturbüro", "Rückfragen, Detailprüfung, verbindliches Angebot."],
              ].map(([k, v], i) => (
                <li key={k} className={`flex gap-4 px-4 py-3 ${i ? "border-t bd" : ""}`}>
                  <span className="f-mono text-sm t-accent num pt-px">{i + 1}</span>
                  <div>
                    <div className="text-sm font-medium t-ink">{k}</div>
                    <div className="text-sm t-mute">{v}</div>
                  </div>
                </li>
              ))}
            </ol>
          }>
          <div className="px-2 py-4 sm:px-8"><SchichtenSkizze /></div>
        </Planblatt>
      </div>
    </div>
  );
}

function SchrittParzelle({ adresse, gefunden, onGefunden, onAndereAdresse }) {
  useEffect(() => {
    if (gefunden) return;
    const t = setTimeout(onGefunden, 1100);
    return () => clearTimeout(t);
  }, [gefunden]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-5 flex flex-col gap-8">
        {gefunden ? (
          <Kopf eyebrow="Parzelle gefunden · Kataster" titel={`Parzelle ${PARZELLE.kennung}`}>
            <p>{PARZELLE.adresse}</p>
          </Kopf>
        ) : (
          <Kopf eyebrow="Kataster wird abgefragt" titel="Parzelle wird gesucht …">
            <p>Adresse: {adresse}</p>
          </Kopf>
        )}

        {gefunden ? (
          <>
            <dl className="border-b bd">
              <Zeile k="Kennung" v={PARZELLE.kennung} />
              <Zeile k="Fläche" v={`${zahl(PARZELLE.flaeche_m2)} m²`} />
              <Zeile k="Straßenfront" v={meter(PARZELLE.strassenfront_m)} />
              <Zeile k="Tiefe" v={meter(PARZELLE.tiefe_m)} />
              <Zeile k="Straßenseite" v={himmelsrichtung(PARZELLE.strassenseite)} />
              <Zeile k="Gartenseite" v={himmelsrichtung(PARZELLE.gartenseite)} />
              <Zeile k="Nachbarn bebaut" v={PARZELLE.nachbarn_bebaut.join(", ")} />
            </dl>
            <p className="text-sm t-mute">
              Nicht Ihr Grundstück? <button type="button" className="link" onClick={onAndereAdresse}>Andere Adresse eingeben</button>
            </p>
            <p className="text-sm t-ink bg-tint px-4 py-3">
              Als Nächstes wertet Emprise den PLU für diese Parzelle aus und zeigt, wo und wie hoch gebaut werden darf.
            </p>
          </>
        ) : (
          <ul className="text-sm t-mute flex flex-col gap-2 f-mono">
            <li>Adresse zugeordnet: Treillières, 44119</li>
            <li>Kataster wird abgefragt …</li>
          </ul>
        )}
      </div>
      <div className="lg:col-span-7">
        <Planblatt inhalt="Lageplan · Bestand" blatt={2}>
          {gefunden ? (
            <Lageplan modus="parzelle" />
          ) : (
            <div className="w-full flex items-center justify-center" style={{ aspectRatio: "46 / 49" }}>
              <span className="eyebrow">Planblatt wird angelegt</span>
            </div>
          )}
        </Planblatt>
      </div>
    </div>
  );
}

function SchrittRegelwerk() {
  const [fokus, setFokus] = useState(null);
  const R = REGELWERK;
  const gruppen = [
    ["Geschosse und Höhen", [
      ["Geschosse max.", `${R.max_geschosse} · EG, OG, ausgebautes Dach`],
      ["Firsthöhe max.", meter(R.max_firsthoehe_m)],
      ["Traufhöhe max.", meter(R.max_traufhoehe_m)],
    ]],
    ["Grundfläche", [
      ["Grundflächenzahl", `${R.grundflaechenzahl_prozent} %`],
      ["Grundfläche max.", `${zahl(R.max_grundflaeche_m2, 1)} m²`],
    ]],
    ["Abstände", [
      ["zur Straße", meter(R.abstand_strasse_m), null, "strasse"],
      ["seitlich", meter(R.abstand_seitlich_m), null, "west"],
      ["hinten", meter(R.abstand_hinten_m), null, "hinten"],
      ["bebaubare Fläche", `${zahl(BEBAUBARE_FLAECHE.breite_m, 1)} × ${zahl(BEBAUBARE_FLAECHE.tiefe_m, 1)} m`, "t-accent font-medium"],
    ]],
    ["Freifläche", [["unversiegelt min.", `${R.unversiegelt_min_prozent} % · ${zahl(R.unversiegelt_min_m2, 1)} m²`]]],
    ["Dach", [
      ["zulässig", R.dachformen_zulaessig.join(", ")],
      ["unzulässig", R.dachformen_unzulaessig.join(", "), "t-alert"],
    ]],
    ["Fassade", [
      ["zulässig", R.fassaden_zulaessig.join(", ")],
      ["unzulässig", R.fassaden_unzulaessig.join(", "), "t-alert"],
    ]],
    ["Energie", [["Norm", `${ENERGIE.norm} · Klimazone ${ENERGIE.klimazone}`]]],
  ];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-5 flex flex-col gap-6">
        <Kopf eyebrow="PLU Treillières · ausgewertet" titel="Was auf dieser Parzelle erlaubt ist">
          <p>Zone {R.zone}. Diese Werte sind ab jetzt die festen Grenzen des Konfigurators.</p>
        </Kopf>
        <div className="border-t bd-strong">
          {gruppen.map(([titel, zeilen]) => (
            <div key={titel} className="regel-zeile grid grid-cols-12 gap-4 py-3">
              <div className="col-span-12 sm:col-span-4 eyebrow pt-0.5">{titel}</div>
              <dl className="col-span-12 sm:col-span-8 flex flex-col gap-1">
                {zeilen.map(([k, v, klasse, regel]) => (
                  <div key={k} className="flex items-baseline justify-between gap-4"
                    onMouseEnter={() => regel && setFokus(regel)} onMouseLeave={() => regel && setFokus(null)}>
                    <dt className="text-sm t-mute">{k}</dt>
                    <dd className={`text-sm text-right num ${klasse || "t-ink"}`}>{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      </div>
      <div className="lg:col-span-7 flex flex-col gap-3">
        <Planblatt inhalt="Lageplan · Regelwerk" blatt={3}>
          <Lageplan modus="regelwerk" fokusRegel={fokus} />
        </Planblatt>
        <p className="text-sm t-mute max-w-prose">
          Nach Abzug von {meter(R.abstand_strasse_m)} zur Straße, je {meter(R.abstand_seitlich_m)} zu den Nachbarn und{" "}
          {meter(R.abstand_hinten_m)} nach hinten bleibt eine bebaubare Fläche von{" "}
          <span className="t-accent font-medium">{zahl(BEBAUBARE_FLAECHE.breite_m, 1)} × {zahl(BEBAUBARE_FLAECHE.tiefe_m, 1)} m</span>.
          Innerhalb dieser Fläche entwerfen Sie.
        </p>
      </div>
    </div>
  );
}

function TypKarte({ typ, gewaehlt, onWaehle, gesperrt, hinweis, kartenRef, linieId, optionen }) {
  const ausloesen = () => onWaehle(typ.id);
  const ueberBreite = typ.abmessung_m[0] > BAUFELD.b;
  return (
    <div ref={kartenRef} role="button" tabIndex={0} aria-pressed={gesperrt ? undefined : gewaehlt} aria-disabled={gesperrt || undefined}
      onClick={ausloesen} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ausloesen(); } }}
      className={`karte ${gesperrt ? "" : "karte-wahl"} flex flex-col md:flex-row`} style={gesperrt ? { cursor: "not-allowed" } : undefined}>
      <div className="md:w-60 xl:w-72 flex-none flex flex-col bg-paper border-b md:border-b-0 md:border-r bd">
        <div className="px-3 pt-2 eyebrow">3D · Südost · Firsthöhe in m</div>
        <div className="flex-1 flex items-end justify-center px-2 pt-1 pb-2">
          <div className="w-full max-w-xs md:max-w-none">
            <Axonometrie typ={typ} linieId={linieId} optionen={optionen} kompakt />
          </div>
        </div>
        <div className="flex items-center gap-3 px-3 py-2 border-t bd">
          <TypSkizze typ={typ} klasse="w-6" />
          <span className="text-xs leading-snug">
            <span className="t-mute block">Grundfläche im Baufeld</span>
            {ueberBreite
              ? <span className="t-alert num">{zahl(typ.abmessung_m[0], 1)} m breit, erlaubt {zahl(BAUFELD.b, 1)} m</span>
              : <span className="t-ink num">{zahl(typ.abmessung_m[0], 1)} von {zahl(BAUFELD.b, 1)} m Breite</span>}
          </span>
        </div>
      </div>
      <div className="flex-1 min-w-0 p-5 flex flex-col gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h3 className={`f-display text-xl font-semibold ${gesperrt ? "t-mute" : "t-ink"}`}>{typ.name}</h3>
          {gesperrt ? <span className="eyebrow t-alert">Auf {PARZELLE.kennung} nicht zulässig</span>
            : gewaehlt ? <span className="eyebrow t-accent">Gewählt</span>
            : <span className="eyebrow">Zulässig</span>}
        </div>
        <p className="text-sm t-mute -mt-2">{typ.kubatur}</p>
        <dl className="grid grid-cols-2 xl:grid-cols-3 gap-x-5 gap-y-2">
          {[
            ["Grundfläche", `${typ.grundflaeche_m2} m²`],
            ["Abmessung", `${zahl(typ.abmessung_m[0], 1)} × ${zahl(typ.abmessung_m[1], 1)} m`],
            ["Wohnfläche", `${typ.wohnflaeche_m2} m²`],
            ["Räume", typ.zimmer],
            ["Dach", typ.dach],
            ["Firsthöhe", meter(typ.firsthoehe_m)],
          ].map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="eyebrow">{k}</dt>
              <dd className={`text-sm num ${gesperrt && (k === "Dach" || k === "Abmessung") ? "t-alert" : "t-ink"}`}>{v}</dd>
            </div>
          ))}
        </dl>
        {gesperrt && (
          <div className="bg-alert px-4 py-3">
            <div className="eyebrow t-alert">Nicht wählbar, weil</div>
            <ul className="mt-1 flex flex-col gap-1">
              {typ.sperrgruende.map((g) => <li key={g} className="text-sm t-ink">— {g}</li>)}
            </ul>
            {hinweis && (
              <p role="status" className="text-sm t-ink mt-2 pt-2 border-t bd-alert">
                Dieser Typ lässt sich hier nicht wählen. Die angepasste Variante direkt darunter hält beide Regeln ein.
              </p>
            )}
          </div>
        )}
        <div className="flex flex-wrap items-end justify-between gap-3 pt-3 border-t bd">
          <div>
            <div className="eyebrow">Basispreis</div>
            <div className={`text-base num ${gesperrt ? "t-faint" : "t-ink"}`}>{eur(typ.basispreis_eur[0])} – {eur(typ.basispreis_eur[1])}</div>
          </div>
          {!gesperrt && (
            <span className={`text-sm font-medium ${gewaehlt ? "t-accent" : "t-ink"}`}>{gewaehlt ? "Ausgewählt" : "Diesen Typ wählen →"}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function SchrittHaustyp({ typId, onWaehle, lage, linieId, optionen }) {
  const [hinweis, setHinweis] = useState(false);
  const adapteRef = useRef(null);
  const [ligne, plateau, adapte] = ["ligne", "plateau", "plateau_adapte"].map(typNach);
  const waehle = (id) => {
    const t = typNach(id);
    if (t.status !== "zulaessig") { setHinweis(true); return; }
    setHinweis(false);
    onWaehle(id);
  };
  const typ = typNach(typId);
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-7 xl:col-span-8 flex flex-col gap-6">
        <Kopf eyebrow="Schritt 4 · Haustyp" titel="Haustyp wählen">
          <p>
            Alle Typen werden gezeigt. Wählbar sind nur die, die das Regelwerk dieser Parzelle einhalten. Die 3D-Ansichten
            stehen im gleichen Maßstab und zeigen die Materialien der Linie {linieId ? linieNach(linieId).name : "Base"}.
          </p>
        </Kopf>
        <TypKarte typ={ligne} gewaehlt={typId === "ligne"} onWaehle={waehle} linieId={linieId} optionen={optionen} />
        <div className="flex flex-col">
          <TypKarte typ={plateau} onWaehle={waehle} gesperrt hinweis={hinweis} linieId={linieId} optionen={optionen} />
          <div className={`border-x bd px-5 py-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 ${hinweis ? "bg-tint" : "bg-paper"}`}>
            <span className="text-sm t-ink">
              <span className="t-accent font-medium">Vorschlag für diese Parzelle:</span> Satteldach 38° statt Flachdach, {meter(adapte.abmessung_m[0])} statt {meter(plateau.abmessung_m[0])} breit.
            </span>
            <button type="button" className="link text-sm" onClick={() => { adapteRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); adapteRef.current?.focus({ preventScroll: true }); }}>
              Zur angepassten Variante ↓
            </button>
          </div>
          <TypKarte typ={adapte} gewaehlt={typId === "plateau_adapte"} onWaehle={waehle} kartenRef={adapteRef} linieId={linieId} optionen={optionen} />
        </div>
      </div>
      <div className="lg:col-span-5 xl:col-span-4 lg:sticky lg:top-6 flex flex-col gap-3">
        <Planblatt inhalt={hinweis ? "Lageplan · Plateau geprüft" : "Lageplan · Grundfläche"} blatt={4}>
          <Lageplan modus="typ" typ={hinweis ? null : typ} lage={lage} vorschauTyp={hinweis ? plateau : null} />
        </Planblatt>
        <p className="text-sm t-mute">
          {hinweis
            ? "Rot schraffiert: der Teil von Plateau, der über die bebaubare Breite hinausragt."
            : typ ? `${typ.name}: ${typ.grundflaeche_m2} m² von max. ${zahl(REGELWERK.max_grundflaeche_m2, 1)} m² Grundfläche. Die genaue Lage legen Sie in Schritt 7 fest.`
            : "Wählen Sie einen Typ, um seine Grundfläche auf der Parzelle zu sehen."}
        </p>
      </div>
    </div>
  );
}

const KATEGORIEN = [...new Set(LINIEN.flatMap((l) => l.umfang.map((u) => umfangTeilen(u)[0])))];

function SchrittLinie({ typ, linieId, onWaehle, optionen }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-7 flex flex-col gap-6">
        <Kopf eyebrow="Schritt 5 · Ausstattung" titel="Ausstattungslinie wählen">
          <p>Die Linie legt Materialien und Haustechnik fest. Der Korridor unten passt sich sofort an.</p>
        </Kopf>
        <div className="overflow-x-auto border bd bg-sheet">
          <table className="w-full text-sm border-collapse" style={{ minWidth: 600 }}>
            <thead>
              <tr>
                <th className="w-28" />
                {LINIEN.map((l) => {
                  const an = l.id === linieId;
                  return (
                    <th key={l.id} scope="col" className={`text-left align-top p-4 border-l bd font-normal ${an ? "bg-tint" : ""}`}>
                      <div className="f-display text-xl font-semibold t-ink">{l.name}</div>
                      <div className="text-sm t-mute num mt-0.5">{l.aufpreis_eur ? caDiff(l.aufpreis_eur) : l.aufpreis_text}</div>
                      <button type="button" aria-pressed={an} onClick={() => onWaehle(l.id)}
                        className={`btn w-full justify-center mt-3 ${an ? "btn-primary" : "btn-ghost"}`}>
                        {an ? "Gewählt" : `${l.name} wählen`}
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {KATEGORIEN.map((kat) => (
                <tr key={kat} className="border-t bd">
                  <th scope="row" className="text-left align-top px-4 py-3 font-normal"><span className="eyebrow">{kat}</span></th>
                  {LINIEN.map((l) => {
                    const eintrag = l.umfang.find((u) => umfangTeilen(u)[0] === kat);
                    return (
                      <td key={l.id} onClick={() => onWaehle(l.id)} className={`align-top px-4 py-3 border-l bd cursor-pointer ${l.id === linieId ? "bg-tint" : ""}`}>
                        {eintrag ? <span className="t-ink">{umfangTeilen(eintrag)[1]}</span> : <span className="t-faint">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {linieId === "base" && (
          <div role="status" className="bg-warn border bd-warn px-5 py-4 flex flex-col gap-1">
            <div className="eyebrow t-warn">{ENERGIE.norm} · Klimazone {ENERGIE.klimazone} · Hinweis</div>
            <p className="t-ink">
              {ENERGIE.befund} ({ENERGIE.kennwert}). Für die Konformität braucht es {ENERGIE.aufpreis_umfang}:{" "}
              <span className="font-medium num whitespace-nowrap">{caDiff(ENERGIE.aufpreis_konformitaet_eur)}</span>.
            </p>
            <p className="text-sm t-mute">Die Linie bleibt wählbar. Der Betrag ist im Korridor eingerechnet und wird im Vorentwurf ausgewiesen.</p>
          </div>
        )}
      </div>
      <div className="lg:col-span-5 lg:sticky lg:top-6">
        <Planblatt inhalt={`Axonometrie · ${typ.name}`} blatt={5} fuss={<MaterialLegende linieId={linieId} optionen={optionen} />}>
          <div className="px-2 py-2"><Axonometrie typ={typ} linieId={linieId} optionen={optionen} /></div>
        </Planblatt>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------
   SCHRITTE 6–9 und Bestätigung
   --------------------------------------------------------------------- */

const AUSSCHLUSS_TEXT = {
  holz_sued: "Wird durch die vollflächige Holzverschalung ersetzt.",
  holz_voll: "Ersetzt die Holzverschalung der Südfassade.",
};

function SchrittOptionen({ typ, linieId, optionen, onUmschalten }) {
  const linie = linieNach(linieId);
  const berechnet = optionen.map(optionNach).filter((o) => !enthalten(o, linieId));
  const summe = berechnet.reduce((s, o) => s + o.aufpreis_eur, 0);
  const inklusive = OPTIONEN.filter((o) => enthalten(o, linieId));
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-7 flex flex-col gap-6">
        <Kopf eyebrow={`Schritt 6 · Linie ${linie.name}`} titel="Materialien und Optionen">
          <p>
            Neben jeder Option steht, was sie zusätzlich kostet. Was in der Linie {linie.name} schon enthalten ist, ist
            markiert und wird nicht noch einmal berechnet.
          </p>
        </Kopf>
        <div className="flex flex-col gap-6">
          {OPTION_GRUPPEN.map((g) => (
            <section key={g.titel}>
              <h3 className="eyebrow pb-2">{g.titel}</h3>
              <div className="border-b bd">
                {g.ids.map((id) => {
                  const o = optionNach(id);
                  const inkl = enthalten(o, linieId);
                  const an = optionen.includes(id);
                  return (
                    <button key={id} type="button" role="checkbox" aria-checked={inkl || an} aria-disabled={inkl || undefined}
                      onClick={() => !inkl && onUmschalten(id)}
                      className={`w-full flex items-center gap-4 py-3 text-left border-t bd ${inkl ? "cursor-default" : ""}`}>
                      <span className="kasten" data-an={an && !inkl} data-inkl={inkl} aria-hidden="true" />
                      <span className="flex-1 min-w-0">
                        <span className={`block ${inkl ? "t-mute" : "t-ink"}`}>{o.name}</span>
                        {AUSSCHLUSS_TEXT[id] && !inkl && <span className="block text-xs t-faint">{AUSSCHLUSS_TEXT[id]}</span>}
                      </span>
                      <span className="text-right num whitespace-nowrap">
                        {inkl ? (
                          <span className="text-sm t-mute">in {linie.name} enthalten · <span className="t-faint">+0&nbsp;€</span></span>
                        ) : (
                          <span className={`text-base ${an ? "t-accent font-medium" : "t-ink"}`}>{caDiff(o.aufpreis_eur)}</span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
        <div className="flex flex-wrap justify-between gap-4 text-sm pt-2">
          <span className="t-mute">
            {inklusive.length ? `${inklusive.length} Optionen sind in ${linie.name} enthalten.` : `Keine Option ist in ${linie.name} enthalten.`}
          </span>
          <span className="t-ink num">
            {berechnet.length ? `${berechnet.length} gewählt · zusammen ${caDiff(summe)}` : "Keine zusätzlichen Optionen gewählt"}
          </span>
        </div>
      </div>
      <div className="lg:col-span-5 lg:sticky lg:top-6">
        <Planblatt inhalt={`Axonometrie · ${typ.name} · ${linie.name}`} blatt={6} fuss={<MaterialLegende linieId={linieId} optionen={optionen} />}>
          <div className="px-2 py-2"><Axonometrie typ={typ} linieId={linieId} optionen={optionen} /></div>
        </Planblatt>
      </div>
    </div>
  );
}

const VOREINSTELLUNGEN = [
  { id: "strassennah", label: "straßennah" },
  { id: "zurueck", label: "zurückversetzt" },
  { id: "suedgarten", label: "Süd-Garten maximal" },
];

function SchrittImplantation({ typ, lage, onLage, onDrehen, verletzt, optionen, linieId }) {
  const a = abstaende(lage, typ);
  const gleich = (p) => Math.abs(p.x - lage.x) < 0.01 && Math.abs(p.y - lage.y) < 0.01 && p.gedreht === lage.gedreht;
  const terrasse = optionen.includes("terrasse");
  const zeilen = [
    ["Straße · Norden", a.strasse, REGELWERK.abstand_strasse_m],
    ["Nachbar West", a.west, REGELWERK.abstand_seitlich_m],
    ["Nachbar Ost", a.ost, REGELWERK.abstand_seitlich_m],
    ["Hintere Grenze · Süden", a.hinten, REGELWERK.abstand_hinten_m],
  ];
  const meldung = verletzt ? REGEL_TEXT[verletzt] : null;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-start">
      <div className="lg:col-span-4 flex flex-col gap-6">
        <Kopf eyebrow="Schritt 7 · Lage auf der Parzelle" titel="Implantation">
          <p>Ziehen Sie den Baukörper innerhalb der bebaubaren Fläche. Über ihre Grenze hinaus lässt er sich nicht schieben.</p>
        </Kopf>
        <div className="flex flex-col gap-2">
          <div className="eyebrow">Schnellauswahl</div>
          <div className="flex flex-wrap gap-2">
            {VOREINSTELLUNGEN.map((v) => {
              const p = voreinstellung(v.id, typ, lage.gedreht);
              return (
                <button key={v.id} type="button" className="chip" aria-pressed={gleich(p)} onClick={() => onLage(p, "voreinstellung")}>{v.label}</button>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-2">
            <button type="button" className="btn btn-ghost" onClick={onDrehen}>Um 90° drehen</button>
            <span className="text-sm t-mute">{lage.gedreht ? "Giebel zur Straße" : "Längsseite nach Süden"}</span>
          </div>
        </div>

        <div role="status" aria-live="polite" className={`px-4 py-3 text-sm ${meldung ? "bg-alert t-ink" : "bg-sheet border bd t-mute"}`}>
          {meldung ? (<><span className="t-alert font-medium">Grenze erreicht.</span> {meldung}.</>) : "Alle Abstände eingehalten."}
        </div>

        <dl className="border-b bd">
          {zeilen.map(([k, v, min]) => (
            <div key={k} className="flex items-baseline justify-between gap-4 py-2 border-t bd">
              <dt className="text-sm t-mute">{k}</dt>
              <dd className="text-sm num text-right">
                <span className="t-ink">{zahl(v, 2)} m</span>
                <span className="t-faint"> · mind. {zahl(min, 1)}</span>
              </dd>
            </div>
          ))}
          <div className="flex items-baseline justify-between gap-4 py-2 border-t bd">
            <dt className="text-sm t-mute">Garten südlich des Hauses</dt>
            <dd className="text-sm num t-ink">{zahl(a.hinten, 2)} m tief · ca. {zahl(Math.round(a.hinten * PARZ_B))} m²</dd>
          </div>
        </dl>
        <p className="text-xs t-faint">Tastatur: Baukörper fokussieren, Pfeiltasten verschieben (mit Umschalt 1 m), R dreht um 90°. Raster {zahl(RASTER_M, 2)} m.</p>
      </div>
      <div className="lg:col-span-8">
        <Planblatt inhalt={`Lageplan · Implantation ${typ.name}`} blatt={7}
          overlay={meldung && (
            <div className="absolute top-5 left-5 bg-alert border bd-alert px-3 py-2 text-sm t-ink pointer-events-none">{meldung}</div>
          )}>
          <Lageplan modus="implantation" typ={typ} lage={lage} onLage={onLage} onDrehen={onDrehen} verletzt={verletzt} terrasse={terrasse} />
        </Planblatt>
      </div>
    </div>
  );
}

function pruefungen(typ, linieId, optionen, lage) {
  const R = REGELWERK;
  const a = abstaende(lage, typ);
  const mat = materialien(linieId, optionen);
  const terr = optionen.includes("terrasse") ? TERRASSE_MASS[0] * TERRASSE_MASS[1] : 0;
  const frei = PARZELLE.flaeche_m2 - typ.grundflaeche_m2 - terr;
  const abst = a.strasse >= R.abstand_strasse_m && a.hinten >= R.abstand_hinten_m && Math.min(a.west, a.ost) >= R.abstand_seitlich_m;
  const fassaden = [...new Set([mat.fassade.name, mat.fassadeSued.name, ...(mat.ziegelEG ? [MATERIAL.ziegel.name] : [])])];
  return [
    { k: "Grundfläche", v: `${typ.grundflaeche_m2} m² von max. ${zahl(R.max_grundflaeche_m2, 1)} m²`, s: typ.grundflaeche_m2 <= R.max_grundflaeche_m2 ? "ok" : "nein" },
    { k: "Firsthöhe", v: `${meter(typ.firsthoehe_m)} von max. ${meter(R.max_firsthoehe_m)}`, s: typ.firsthoehe_m <= R.max_firsthoehe_m ? "ok" : "nein" },
    typ.traufhoehe_m
      ? { k: "Traufhöhe", v: `${meter(typ.traufhoehe_m)} von max. ${meter(R.max_traufhoehe_m)}`, s: typ.traufhoehe_m <= R.max_traufhoehe_m ? "ok" : "nein" }
      : { k: "Traufhöhe", v: "in den Typdaten nicht angegeben", s: "offen" },
    { k: "Dachform", v: `${typ.dach} · zulässig: ${R.dachformen_zulaessig[0]}`, s: "ok" },
    { k: "Abstände", v: `Straße ${zahl(a.strasse, 2)} · West ${zahl(a.west, 2)} · Ost ${zahl(a.ost, 2)} · hinten ${zahl(a.hinten, 2)} m`, s: abst ? "ok" : "nein" },
    { k: "Unversiegelt", v: `rechnerisch ca. ${zahl(frei)} m² von mind. ${zahl(R.unversiegelt_min_m2, 1)} m², vor Zufahrt und Wegen${optionen.includes("carport") ? " und Carport" : ""}`, s: frei >= R.unversiegelt_min_m2 ? "ok" : "nein" },
    { k: "Fassade", v: fassaden.join(", "), s: "ok" },
    linieId === "base"
      ? { k: ENERGIE.norm, v: `${ENERGIE.befund}. Konformität eingerechnet, ${caDiff(ENERGIE.aufpreis_konformitaet_eur)}`, s: "eingerechnet" }
      : { k: ENERGIE.norm, v: `Für die Linie ${linieNach(linieId).name} liegt kein Befund vor`, s: "ok" },
  ];
}

const STATUS = {
  ok: ["erfüllt", "t-ink bd-strong"],
  eingerechnet: ["eingerechnet", "t-warn bd-warn"],
  offen: ["prüft das Büro", "t-mute bd"],
  nein: ["verletzt", "t-alert bd-alert"],
};

function Abschnitt({ titel, schritt, onGehe, children }) {
  return (
    <div className="grid grid-cols-12 gap-4 py-4 border-t bd">
      <div className="col-span-12 sm:col-span-3 eyebrow pt-0.5">{titel}</div>
      <div className="col-span-10 sm:col-span-7 text-sm t-ink flex flex-col gap-1">{children}</div>
      <div className="col-span-2 text-right">
        {onGehe && <button type="button" className="link text-sm" onClick={() => onGehe(schritt)}>Ändern</button>}
      </div>
    </div>
  );
}

function Angaben({ typ, linieId, optionen, lage, onGehe }) {
  const linie = linieNach(linieId);
  const a = abstaende(lage, typ);
  return (
    <div className="border-b bd">
      <Abschnitt titel="Parzelle" schritt={1} onGehe={onGehe}>
        <span>{PARZELLE.kennung} · {zahl(PARZELLE.flaeche_m2)} m² · Zone UB</span>
        <span className="t-mute">{PARZELLE.adresse}</span>
      </Abschnitt>
      <Abschnitt titel="Haustyp" schritt={4} onGehe={onGehe}>
        <span>{typ.name} · {typ.kubatur}</span>
        <span className="t-mute">{typ.grundflaeche_m2} m² Grundfläche · {typ.wohnflaeche_m2} m² Wohnfläche · {typ.zimmer} · {typ.dach}</span>
      </Abschnitt>
      <Abschnitt titel="Ausstattungslinie" schritt={5} onGehe={onGehe}>
        <span>{linie.name} · <span className="num">{linie.aufpreis_eur ? caDiff(linie.aufpreis_eur) : linie.aufpreis_text}</span></span>
        {linieId === "base" && <span className="t-warn">RE2020-Konformität {caDiff(ENERGIE.aufpreis_konformitaet_eur)} ({ENERGIE.aufpreis_umfang})</span>}
      </Abschnitt>
      <Abschnitt titel="Optionen" schritt={6} onGehe={onGehe}>
        {optionen.length === 0 && OPTIONEN.every((o) => !enthalten(o, linieId)) && <span className="t-mute">Keine Optionen gewählt</span>}
        {OPTIONEN.filter((o) => optionen.includes(o.id) || enthalten(o, linieId)).map((o) => (
          <span key={o.id} className="flex justify-between gap-4">
            <span>{o.name}</span>
            <span className="num whitespace-nowrap t-mute">{enthalten(o, linieId) ? `in ${linie.name} enthalten` : caDiff(o.aufpreis_eur)}</span>
          </span>
        ))}
      </Abschnitt>
      <Abschnitt titel="Implantation" schritt={7} onGehe={onGehe}>
        <span>{lage.gedreht ? "Giebel zur Straße" : "Längsseite nach Süden"}</span>
        <span className="t-mute num">Straße {zahl(a.strasse, 2)} m · West {zahl(a.west, 2)} m · Ost {zahl(a.ost, 2)} m · Garten {zahl(a.hinten, 2)} m tief</span>
      </Abschnitt>
    </div>
  );
}

function SchrittZusammenfassung({ typ, linieId, optionen, lage, korridor, onGehe }) {
  const pr = pruefungen(typ, linieId, optionen, lage);
  return (
    <div className="flex flex-col gap-10">
      <Kopf eyebrow="Schritt 8 · Vorentwurf zur Prüfung" titel={`Ihr Vorentwurf für Parzelle ${PARZELLE.kennung}`}>
        <p>Alle Angaben auf einem Blatt. Jeder Punkt lässt sich noch ändern, Ihre übrigen Entscheidungen bleiben dabei erhalten.</p>
      </Kopf>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-5">
          <Planblatt inhalt="Lageplan" blatt={8}>
            <Lageplan modus="uebersicht" typ={typ} lage={lage} terrasse={optionen.includes("terrasse")} />
          </Planblatt>
        </div>
        <div className="lg:col-span-7">
          <Planblatt inhalt={`Axonometrie · ${typ.name} · ${linieNach(linieId).name}`} blatt={8} fuss={<MaterialLegende linieId={linieId} optionen={optionen} />}>
            <div className="px-4 py-4"><Axonometrie typ={typ} linieId={linieId} optionen={optionen} /></div>
          </Planblatt>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
        <section className="lg:col-span-7">
          <h3 className="f-display text-xl font-semibold t-ink pb-3">Angaben</h3>
          <Angaben typ={typ} linieId={linieId} optionen={optionen} lage={lage} onGehe={onGehe} />
        </section>
        <section className="lg:col-span-5 flex flex-col gap-8">
          <div>
            <h3 className="f-display text-xl font-semibold t-ink pb-3">Abgleich mit dem Regelwerk</h3>
            <ul className="border-b bd">
              {pr.map((p) => (
                <li key={p.k} className="flex items-start justify-between gap-4 py-2 border-t bd">
                  <div className="min-w-0">
                    <div className="text-sm t-ink">{p.k}</div>
                    <div className="text-xs t-mute num">{p.v}</div>
                  </div>
                  <span className={`eyebrow border px-2 py-0.5 whitespace-nowrap ${STATUS[p.s][1]}`}>{STATUS[p.s][0]}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="border bd-strong bg-sheet p-5 flex flex-col gap-2">
            <div className="eyebrow">Kostenkorridor · Schätzung</div>
            <div className="f-display text-3xl font-semibold t-ink num">ca. {zahl(rund(korridor.lo))} – {zahl(rund(korridor.hi))}&nbsp;€</div>
            <dl className="mt-2">
              {korridor.posten.map((p) => (
                <div key={p.label} className="flex justify-between gap-4 py-1.5 border-t bd text-sm">
                  <dt className="t-mute">{p.label}</dt>
                  <dd className={`num ${p.warn ? "t-warn" : "t-ink"}`}>{p.text}</dd>
                </div>
              ))}
            </dl>
            <p className="text-xs t-mute mt-2">Verbindlich wird ein Preis erst mit dem Angebot des Architekturbüros nach Prüfung des Vorentwurfs.</p>
          </div>
        </section>
      </div>
    </div>
  );
}

const BAUBEGINN = ["in den nächsten 6 Monaten", "in 6 bis 12 Monaten", "in 12 bis 24 Monaten", "noch offen"];
const labelText = (s) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/\s*\(ja\/nein\)/, "");

function SchrittKontakt({ kontakt, setKontakt, bestaetigt, setBestaetigt, onSenden, typ, linieId, optionen, korridor }) {
  const [versuch, setVersuch] = useState(false);
  const [lName, lMail, lTel, lBeginn, lFin] = KONTAKTFORMULAR.map(labelText);
  const fehler = {
    name: !kontakt.name.trim() ? "Bitte Ihren Namen angeben." : null,
    email: !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(kontakt.email.trim()) ? "Bitte eine gültige E-Mail-Adresse angeben, z. B. name@beispiel.fr." : null,
  };
  const setze = (feld) => (e) => setKontakt({ ...kontakt, [feld]: e.target.value });
  const senden = () => {
    setVersuch(true);
    if (fehler.name || fehler.email || !bestaetigt) return;
    onSenden();
  };
  const linie = linieNach(linieId);
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-7 flex flex-col gap-8">
        <Kopf eyebrow="Schritt 9 · Übergabe an das Architekturbüro" titel="Wohin soll die Rückmeldung gehen?">
          <p>Das Büro prüft Ihren Vorentwurf und meldet sich mit Rückfragen oder einem verbindlichen Angebot. Mit dem Absenden entsteht kein Vertrag.</p>
        </Kopf>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="k-name" className="text-sm font-medium t-ink">{lName}</label>
            <input id="k-name" className="field" value={kontakt.name} onChange={setze("name")} autoComplete="name" aria-invalid={versuch && !!fehler.name} />
            {versuch && fehler.name && <span className="text-xs t-alert">{fehler.name}</span>}
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="k-mail" className="text-sm font-medium t-ink">{lMail}</label>
            <input id="k-mail" type="email" className="field" value={kontakt.email} onChange={setze("email")} autoComplete="email" aria-invalid={versuch && !!fehler.email} />
            {versuch && fehler.email && <span className="text-xs t-alert">{fehler.email}</span>}
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="k-tel" className="text-sm font-medium t-ink">{lTel} <span className="t-faint font-normal">optional</span></label>
            <input id="k-tel" type="tel" className="field" value={kontakt.telefon} onChange={setze("telefon")} autoComplete="tel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="k-beginn" className="text-sm font-medium t-ink">{lBeginn}</label>
            <select id="k-beginn" className="field" value={kontakt.baubeginn} onChange={setze("baubeginn")}>
              <option value="">Bitte wählen</option>
              {BAUBEGINN.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <span id="k-fin" className="text-sm font-medium t-ink">{lFin}</span>
            <div role="radiogroup" aria-labelledby="k-fin" className="flex gap-2">
              {["ja", "nein"].map((w) => (
                <button key={w} type="button" role="radio" aria-checked={kontakt.finanzierung === w} aria-pressed={kontakt.finanzierung === w}
                  className="chip min-w-20" onClick={() => setKontakt({ ...kontakt, finanzierung: w })}>
                  {w === "ja" ? "Ja" : "Nein"}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button type="button" role="checkbox" aria-checked={bestaetigt} onClick={() => setBestaetigt(!bestaetigt)}
          className={`flex items-start gap-4 text-left border px-5 py-4 ${versuch && !bestaetigt ? "bd-alert" : bestaetigt ? "bd-accent" : "bd-strong"} bg-sheet`}>
          <span className="kasten mt-0.5" data-an={bestaetigt} aria-hidden="true" />
          <span className="flex flex-col gap-1">
            <span className="t-ink font-medium">Mir ist bewusst, dass ich eine unverbindliche Vorentwurfsskizze übergebe.</span>
            <span className="text-sm t-mute">Alle Beträge sind Schätzspannen. Verbindlich ist erst das Angebot des Architekturbüros nach dessen Prüfung.</span>
            {versuch && !bestaetigt && <span className="text-sm t-alert">Bitte bestätigen Sie diesen Punkt, um den Vorentwurf zu übergeben.</span>}
          </span>
        </button>

        <div className="flex flex-wrap items-center gap-4">
          <button type="button" className="btn btn-primary" onClick={senden}>Vorentwurf zur Prüfung übergeben</button>
          <span className="text-sm t-mute">Keine Zahlung, kein Vertrag.</span>
        </div>
      </div>

      <aside className="lg:col-span-5 flex flex-col gap-6">
        <div className="border bd-strong bg-sheet">
          <div className="px-5 py-3 border-b bd eyebrow">Das wird übergeben</div>
          <dl className="px-5 pb-2">
            {[
              ["Parzelle", `${PARZELLE.kennung} · Treillières`],
              ["Haustyp", typ.name],
              ["Linie", linie.name],
              ["Optionen", `${optionen.filter((id) => !enthalten(optionNach(id), linieId)).length} gewählt`],
              ["Lageplan und Axonometrie", "Blatt 8"],
              ["Korridor", `ca. ${zahl(rund(korridor.lo))} – ${zahl(rund(korridor.hi))} €`],
            ].map(([k, v], i) => (
              <div key={k} className={`flex justify-between gap-4 py-2 text-sm ${i ? "border-t bd" : ""}`}>
                <dt className="t-mute">{k}</dt><dd className="t-ink num text-right">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <Ablauf />
      </aside>
    </div>
  );
}

function Ablauf() {
  return (
    <div>
      <div className="eyebrow pb-2">Wie es weitergeht</div>
      <ol className="border-b bd">
        {[
          ["Prüfung", "Das Architekturbüro prüft den Vorentwurf gegen den PLU und die Machbarkeit."],
          ["Rückmeldung", "Rückfragen per Telefon oder E-Mail, bei Bedarf ein Gespräch."],
          ["Angebot", "Sie erhalten ein verbindliches Angebot. Erst dann entscheiden Sie."],
        ].map(([k, v], i) => (
          <li key={k} className="flex gap-4 py-3 border-t bd">
            <span className="f-mono text-sm t-accent num">{i + 1}</span>
            <div><div className="text-sm font-medium t-ink">{k}</div><div className="text-sm t-mute">{v}</div></div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Bestaetigung({ kontakt, typ, linieId, optionen, lage }) {
  const vorgang = useMemo(() => {
    const d = new Date();
    return `VE-${PARZELLE.kennung.replace(/\s/g, "")}-${String(d.getDate()).padStart(2, "0")}${String(d.getMonth() + 1).padStart(2, "0")}`;
  }, []);
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
      <div className="lg:col-span-6 flex flex-col gap-8">
        <Kopf gross eyebrow={`Übergeben · Vorgang ${vorgang}`} titel="Ihr Vorentwurf liegt jetzt beim Architekturbüro.">
          <p>
            Der Vorentwurf für Parzelle {PARZELLE.kennung} ist zur Prüfung übergeben. Eine Kopie mit allen Angaben geht an{" "}
            <span className="t-ink">{kontakt.email}</span>.
          </p>
        </Kopf>
        <Ablauf />
        <p className="text-sm t-mute max-w-prose">
          Sie haben nichts gekauft und nichts unterschrieben. Die Beträge im Vorentwurf bleiben Schätzspannen, bis das Büro sein Angebot vorlegt.
        </p>
      </div>
      <div className="lg:col-span-6 flex flex-col gap-4">
        <Planblatt inhalt={`Vorentwurf · ${typ.name} · ${linieNach(linieId).name}`} blatt={9}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-center">
            <Lageplan modus="uebersicht" typ={typ} lage={lage} terrasse={optionen.includes("terrasse")} />
            <Axonometrie typ={typ} linieId={linieId} optionen={optionen} />
          </div>
        </Planblatt>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------
   APP — Zustand ausschließlich über React-State
   --------------------------------------------------------------------- */

export default function Hauskonfigurator() {
  const [schritt, setSchritt] = useState(1);
  const [maxSchritt, setMaxSchritt] = useState(1);
  const [adresse, setAdresse] = useState(PARZELLE.adresse);
  const [gefunden, setGefunden] = useState(false);
  const [typId, setTypId] = useState(null);
  const [linieId, setLinieId] = useState(null);
  const [optionen, setOptionen] = useState([]);
  const [lage, setLage] = useState({ x: 4, y: BAUFELD.y, gedreht: false });
  const [verletzt, setVerletzt] = useState(null);
  const [kontakt, setKontakt] = useState({ name: "", email: "", telefon: "", baubeginn: "", finanzierung: "" });
  const [bestaetigt, setBestaetigt] = useState(false);
  const [gesendet, setGesendet] = useState(false);
  const meldeTimer = useRef(null);

  const typ = typNach(typId);
  const korridor = useMemo(() => korridorBerechnen({ schritt, typId, linieId, optionen }), [schritt, typId, linieId, optionen]);

  useEffect(() => () => clearTimeout(meldeTimer.current), []);

  const gehe = (n) => {
    setSchritt(n);
    setMaxSchritt((m) => Math.max(m, n));
    window.scrollTo(0, 0);
  };

  const typWaehlen = (id) => {
    const neu = typNach(id);
    setLage((l) => (typId ? lageBegrenzen(l, neu).lage : voreinstellung("strassennah", neu, false)));
    setTypId(id);
  };

  const umschalten = (id) => {
    setOptionen((alt) => {
      if (alt.includes(id)) return alt.filter((x) => x !== id);
      const ohne = alt.filter((x) => !(AUSSCHLUESSE[id] || []).includes(x));
      return [...ohne, id];
    });
  };

  const melden = (regel) => {
    setVerletzt(regel);
    clearTimeout(meldeTimer.current);
    meldeTimer.current = setTimeout(() => setVerletzt(null), 2400);
  };

  const lageSetzen = (neu) => {
    const r = lageBegrenzen(neu, typ);
    setLage(r.lage);
    if (r.verletzt) melden(r.verletzt);
  };

  const drehen = () => {
    const m = planMass(typ, lage.gedreht);
    const n = planMass(typ, !lage.gedreht);
    const runden = (v) => Math.round(v / RASTER_M) * RASTER_M;
    const neu = {
      gedreht: !lage.gedreht,
      x: runden(lage.x + m.b / 2 - n.b / 2),
      y: runden(lage.y + m.t / 2 - n.t / 2),
    };
    setLage(lageBegrenzen(neu, typ).lage);
  };

  const weiterNach = {
    2: { label: "Weiter zum Regelwerk", aktiv: gefunden, grund: "Die Parzelle wird noch gesucht." },
    3: { label: "Weiter: Haustyp", aktiv: true },
    4: { label: "Weiter: Ausstattungslinie", aktiv: !!typ, grund: "Bitte einen zulässigen Haustyp wählen." },
    5: { label: "Weiter: Optionen", aktiv: !!linieId, grund: "Bitte eine Ausstattungslinie wählen." },
    6: { label: "Weiter: Implantation", aktiv: true },
    7: { label: "Weiter: Vorentwurf", aktiv: true },
    8: { label: "Weiter: Übergabe", aktiv: true },
  };
  const weiter = !gesendet && weiterNach[schritt] ? { ...weiterNach[schritt], aktion: () => gehe(schritt + 1) } : null;

  let inhalt;
  if (gesendet) {
    inhalt = <Bestaetigung kontakt={kontakt} typ={typ} linieId={linieId} optionen={optionen} lage={lage} />;
  } else if (schritt === 1) {
    inhalt = <SchrittStart adresse={adresse} setAdresse={setAdresse} onSuchen={() => gehe(2)} />;
  } else if (schritt === 2) {
    inhalt = <SchrittParzelle adresse={adresse} gefunden={gefunden} onGefunden={() => setGefunden(true)} onAndereAdresse={() => gehe(1)} />;
  } else if (schritt === 3) {
    inhalt = <SchrittRegelwerk />;
  } else if (schritt === 4) {
    inhalt = <SchrittHaustyp typId={typId} onWaehle={typWaehlen} lage={lage} linieId={linieId} optionen={optionen} />;
  } else if (schritt === 5) {
    inhalt = <SchrittLinie typ={typ} linieId={linieId} onWaehle={setLinieId} optionen={optionen} />;
  } else if (schritt === 6) {
    inhalt = <SchrittOptionen typ={typ} linieId={linieId} optionen={optionen} onUmschalten={umschalten} />;
  } else if (schritt === 7) {
    inhalt = <SchrittImplantation typ={typ} lage={lage} onLage={lageSetzen} onDrehen={drehen} verletzt={verletzt} optionen={optionen} linieId={linieId} />;
  } else if (schritt === 8) {
    inhalt = <SchrittZusammenfassung typ={typ} linieId={linieId} optionen={optionen} lage={lage} korridor={korridor} onGehe={gehe} />;
  } else {
    inhalt = (
      <SchrittKontakt kontakt={kontakt} setKontakt={setKontakt} bestaetigt={bestaetigt} setBestaetigt={setBestaetigt}
        onSenden={() => { setGesendet(true); window.scrollTo(0, 0); }} typ={typ} linieId={linieId} optionen={optionen} korridor={korridor} />
    );
  }

  return (
    <div className="emp min-h-screen">
      <style>{STIL}</style>
      <Kopfzeile schritt={schritt} maxSchritt={maxSchritt} onGehe={gehe} gesendet={gesendet} />
      <main className="max-w-7xl mx-auto px-6 lg:px-10 pt-10 pb-56">
        <div key={gesendet ? "fertig" : schritt} className="anim-seite">{inhalt}</div>
      </main>
      <Korridorbalken korridor={korridor} weiter={weiter}
        zurueckAktiv={gesendet ? null : schritt > 1}
        onZurueck={() => gehe(Math.max(1, schritt - 1))} />
    </div>
  );
}
