const { contextBridge } = require("electron");

const API = "http://127.0.0.1:43128";

async function request(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

contextBridge.exposeInMainWorld("comicTranslator", {
  apiBaseUrl: API,
  getHealth: () => request("/health"),
  listProjects: () => request("/api/v1/projects"),
  createProject: (project) => request("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(project)
  }),
  getProject: (id) => request("/api/v1/projects/" + encodeURIComponent(id))
});
