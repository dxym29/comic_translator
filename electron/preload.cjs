const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("comicTranslator", {
  apiBaseUrl: "http://127.0.0.1:43128",
  getHealth: async () => {
    const response = await fetch("http://127.0.0.1:43128/health");
    if (!response.ok) throw new Error("Local service is not ready");
    return response.json();
  }
});
