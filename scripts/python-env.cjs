const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

function resolvePython() {
  const candidates = process.platform === "win32"
    ? [path.join(root, ".venv", "Scripts", "python.exe")]
    : [path.join(root, ".venv", "bin", "python")];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }

  throw new Error(
    "Comic Translator Python environment was not found. Create/install the project .venv first. " +
    "Expected: " + candidates[0]
  );
}

module.exports = { root, resolvePython };
