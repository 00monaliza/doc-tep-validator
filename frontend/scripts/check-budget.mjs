// Platform chunks must not pull three.js, and the entry stays small (spec §7).
import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const dir = new URL("../dist/assets/", import.meta.url);
const files = readdirSync(dir).filter(f => f.endsWith(".js"));
// the entry is the script dist/index.html loads (several chunks are named index-*)
const html = readFileSync(new URL("../dist/index.html", import.meta.url), "utf8");
const entry = html.match(/src="\/assets\/([^"]+\.js)"/)[1];
const kb = f => gzipSync(readFileSync(new URL(f, dir))).length / 1024;
let failed = false;
if (kb(entry) > 200) { console.error(`entry ${entry}: ${kb(entry).toFixed(0)} KB gzip > 200`); failed = true; }
// three.js ships the WebGLRenderer class: only the landing scene chunk (plan 2) may contain it
for (const f of files) if (readFileSync(new URL(f, dir), "utf8").includes("WebGLRenderer") && !/scene/i.test(f)) {
  console.error(`${f} pulls three.js into the platform`); failed = true;
}
console.log(files.map(f => `${f}: ${kb(f).toFixed(0)} KB`).join("\n"));
process.exit(failed ? 1 : 0);
