// Übersetzt Hauskonfigurator.jsx in die eigenständige Seite emprise.html.
// Voraussetzung (einmalig): npm install --no-save esbuild
// Aufruf aus dem Projektordner: node tools/build-mockup.cjs
const fs = require("fs");
const path = require("path");
const esbuild = require("esbuild");

const root = path.resolve(__dirname, "..");
const src = path.join(root, "Hauskonfigurator.jsx");
const out = path.join(root, "emprise.html");

let code = fs.readFileSync(src, "utf8");
code = code.replace(/^import React, \{([^}]*)\} from "react";/m, (_, names) => `const {${names}} = React;`);
code = code.replace("export default function Hauskonfigurator", "function Hauskonfigurator");
code += `\nReactDOM.createRoot(document.getElementById("root")).render(React.createElement(Hauskonfigurator));\n`;

const js = esbuild.transformSync(code, {
  loader: "jsx",
  jsx: "transform",
  jsxFactory: "React.createElement",
  jsxFragment: "React.Fragment",
  target: "es2019",
}).code;

const html = `<title>Emprise Hauskonfigurator</title>
<meta name="description" content="Klickbares Mockup: regelbasierter Vorentwurf auf Parzelle AB 0147, Treillières">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>body{background:#F3F4F1}@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) body{background:#111413}}:root[data-theme="dark"] body{background:#111413}</style>
<script src="https://cdn.tailwindcss.com/3.4.16"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>
<div id="root"></div>
<script>
${js.replace(/<\/script/gi, "<\\/script")}
</script>
`;

fs.writeFileSync(out, html);
console.log(`emprise.html geschrieben (${html.length} Zeichen)`);
