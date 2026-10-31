/**
 * prepare-public.cjs — runs as part of `npm run build` (before `vite build`).
 *
 * Copies the pipeline-generated payloads into web/src/ so the TypeScript
 * bundle always ships the exact JSON the Python engine produced:
 *   data/risk_tables.json      -> src/risk_tables.json
 *   data/test-vectors.json     -> src/test-vectors.json
 *   data/outputs/book.json     -> src/book.json
 *   data/outputs/rescue.json   -> src/rescue.json
 *   data/outputs/summary.json  -> src/summary.json
 * Exits non-zero if any payload is missing, unparseable, or empty.
 */
const fs = require("node:fs");
const path = require("node:path");

const WEB_DIR = path.resolve(__dirname, "..");
const ROOT_DIR = path.resolve(WEB_DIR, "..");
const SRC_DIR = path.join(WEB_DIR, "src");

const FILES = [
  ["data", "risk_tables.json"],
  ["data", "test-vectors.json"],
  ["data", "outputs", "book.json"],
  ["data", "outputs", "rescue.json"],
  ["data", "outputs", "summary.json"],
];

function fail(msg) {
  console.error(`prepare-public: ${msg}`);
  process.exit(1);
}

for (const parts of FILES) {
  const srcPath = path.join(ROOT_DIR, ...parts);
  const dstPath = path.join(SRC_DIR, parts[parts.length - 1]);
  if (!fs.existsSync(srcPath)) {
    fail(`${path.relative(ROOT_DIR, srcPath)} missing`);
  }
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(srcPath, "utf8"));
  } catch (e) {
    fail(`${path.relative(ROOT_DIR, srcPath)} is not valid JSON (${e && e.message ? e.message : e})`);
  }
  if (payload === null || (Array.isArray(payload) && payload.length === 0)) {
    fail(`${path.relative(ROOT_DIR, srcPath)} is empty`);
  }
  fs.copyFileSync(srcPath, dstPath);
  console.log(`prepare-public: ${path.relative(ROOT_DIR, srcPath)} -> src/${parts[parts.length - 1]}`);
}

// Sanity checks on the shipped payloads.
const vectors = JSON.parse(fs.readFileSync(path.join(SRC_DIR, "test-vectors.json"), "utf8"));
if (!Array.isArray(vectors.vectors) || vectors.vectors.length !== 12) {
  fail(`test-vectors.json must hold exactly 12 vectors (found ${Array.isArray(vectors.vectors) ? vectors.vectors.length : "none"})`);
}
const rescue = JSON.parse(fs.readFileSync(path.join(SRC_DIR, "rescue.json"), "utf8"));
if (!Array.isArray(rescue) || rescue.length === 0) {
  fail("rescue.json is empty");
}
const summary = JSON.parse(fs.readFileSync(path.join(SRC_DIR, "summary.json"), "utf8"));
if (!summary || summary.n_appointments !== rescue.length) {
  fail("summary.json n_appointments does not match rescue.json length");
}
console.log(`prepare-public: ${vectors.vectors.length} test vectors, ${rescue.length} rescue rows, summary OK`);
