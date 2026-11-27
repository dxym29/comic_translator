const { app, BrowserWindow } = require("electron");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { root, resolvePython } = require("../scripts/python-env.cjs");

let mainWindow;
let backendProcess;

function startBackend() {
  let python;
  try {
    python = resolvePython();
  } catch (error) {
    console.error(error.message);
    const { dialog } = require("electron");
    dialog.showErrorBox("Python environment missing", error.message);
    app.quit();
    return;
  }
  backendProcess = spawn(python, ["-m", "backend"], {
    cwd: root,
    env: { ...process.env, COMIC_TRANSLATOR_HOST: "127.0.0.1", COMIC_TRANSLATOR_PORT: "43128" },
    stdio: "inherit",
    windowsHide: true
  });
  backendProcess.on("error", (error) => {
    console.error("Could not start the local Python service:", error);
  });
  backendProcess.on("exit", (code) => {
    if (code !== null && code !== 0) console.error("Local Python service exited with code", code);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: "#111318",
    title: "Comic Translator",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.loadFile(path.join(__dirname, "..", "src", "index.html"));
  mainWindow.on("closed", () => { mainWindow = null; });
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) backendProcess.kill();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
