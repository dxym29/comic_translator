const { spawn } = require("node:child_process");
const { root, resolvePython } = require("./python-env.cjs");

let python;
try {
  python = resolvePython();
} catch (error) {
  console.error(error.message);
  process.exit(1);
}

const child = spawn(python, ["-m", "backend"], {
  cwd: root,
  env: { ...process.env },
  stdio: "inherit",
  windowsHide: true
});
child.on("error", error => {
  console.error("Could not start Comic Translator backend:", error);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exitCode = code ?? 1;
});
