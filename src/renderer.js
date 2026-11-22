const statusText = document.getElementById("service-status");
const statusDot = document.querySelector(".status-dot");
const projectList = document.getElementById("project-list");
const createButton = document.getElementById("create-project");
const dialog = document.getElementById("project-dialog");
const form = document.getElementById("project-form");
const message = document.getElementById("form-message");
const workspace = document.getElementById("project-workspace");
const workspaceTitle = document.getElementById("workspace-title");
const imageInput = document.getElementById("comic-image");
const previewImage = document.getElementById("comic-preview");
const detectButton = document.getElementById("detect-text");
const cleanButton = document.getElementById("clean-image");
const ocrMessage = document.getElementById("ocr-message");
const regionList = document.getElementById("region-list");
const regionCount = document.getElementById("region-count");
const downloadCleaned = document.getElementById("download-cleaned");

let selectedProject = null;
let selectedFile = null;
let detectedRegions = [];
let sourceObjectUrl = null;
let cleanedObjectUrl = null;

async function checkLocalEngine() {
  try {
    const health = await window.comicTranslator.getHealth();
    statusText.textContent = health.status === "ok" ? "Local engine connected" : "Local engine unavailable";
    statusDot.classList.toggle("online", health.status === "ok");
    await loadProjects();
  } catch {
    statusText.textContent = "Waiting for local engine";
    statusDot.classList.remove("online");
    projectList.innerHTML = '<div class="empty-state">Local engine is starting. Please wait a moment.</div>';
    setTimeout(checkLocalEngine, 1500);
  }
}

async function loadProjects() {
  const result = await window.comicTranslator.listProjects();
  if (!result.projects.length) {
    projectList.innerHTML = '<div class="empty-state">No projects yet. Create your first comic project to get started.</div>';
    return;
  }
  projectList.innerHTML = "";
  for (const project of result.projects) {
    const card = document.createElement("article");
    card.className = "project-row";
    const details = document.createElement("div");
    details.className = "project-row-details";
    const title = document.createElement("strong");
    title.textContent = project.name;
    const description = document.createElement("span");
    description.textContent = `${project.source_language} → ${project.target_language} · ${project.typesetting_style === "professional" ? "Professional Typesetting" : "Original Bubble Style"}`;
    details.append(title, description);
    const date = document.createElement("small");
    date.textContent = new Date(project.updated_at).toLocaleString();
    const open = document.createElement("button");
    open.className = "secondary-button";
    open.textContent = "Open project";
    open.addEventListener("click", () => openProject(project));
    card.append(details, date, open);
    projectList.append(card);
  }
}

function openProject(project) {
  selectedProject = project;
  workspaceTitle.textContent = project.name + " · OCR Preview";
  workspace.hidden = false;
  workspace.scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetOcrResults() {
  detectedRegions = [];
  regionCount.textContent = "0";
  regionList.innerHTML = '<div class="empty-state">No OCR results yet.</div>';
  cleanButton.disabled = true;
  downloadCleaned.hidden = true;
  if (cleanedObjectUrl) URL.revokeObjectURL(cleanedObjectUrl);
  cleanedObjectUrl = null;
}

createButton.addEventListener("click", () => {
  message.textContent = "";
  dialog.showModal();
});

document.getElementById("cancel-project").addEventListener("click", () => dialog.close());
document.getElementById("cancel-project-secondary").addEventListener("click", () => dialog.close());
document.getElementById("close-workspace").addEventListener("click", () => {
  workspace.hidden = true;
  selectedProject = null;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const project = {
    name: data.get("name"),
    source_language: data.get("source_language"),
    target_language: data.get("target_language"),
    typesetting_style: data.get("typesetting_style"),
    font_family: data.get("font_family"),
    source_url: data.get("source_url")
  };
  const submit = form.querySelector('button[type="submit"]');
  submit.disabled = true;
  message.textContent = "Creating project…";
  try {
    await window.comicTranslator.createProject(project);
    form.reset();
    dialog.close();
    await loadProjects();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

imageInput.addEventListener("change", () => {
  selectedFile = imageInput.files?.[0] || null;
  resetOcrResults();
  detectButton.disabled = !selectedFile;
  if (sourceObjectUrl) URL.revokeObjectURL(sourceObjectUrl);
  sourceObjectUrl = selectedFile ? URL.createObjectURL(selectedFile) : null;
  previewImage.hidden = !sourceObjectUrl;
  if (sourceObjectUrl) previewImage.src = sourceObjectUrl;
  ocrMessage.textContent = selectedFile ? `Selected: ${selectedFile.name}. Original image is kept unchanged.` : "Choose one image to test local OCR.";
});

detectButton.addEventListener("click", async () => {
  if (!selectedFile || !selectedProject) return;
  detectButton.disabled = true;
  cleanButton.disabled = true;
  ocrMessage.textContent = "Running CPU OCR. The first run may download model files and take longer.";
  try {
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("language", document.getElementById("ocr-language").value);
    const response = await fetch(window.comicTranslator.apiBaseUrl + "/api/v1/images/ocr-preview", { method: "POST", body });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "OCR request failed");
    detectedRegions = result.regions;
    renderRegions();
    ocrMessage.textContent = `Detected ${result.count} text lines in ${result.width} × ${result.height} image. Review the boxes before cleanup.`;
    cleanButton.disabled = detectedRegions.length === 0;
  } catch (error) {
    ocrMessage.textContent = error.message;
  } finally {
    detectButton.disabled = !selectedFile;
  }
});

function renderRegions() {
  regionCount.textContent = String(detectedRegions.length);
  regionList.innerHTML = "";
  if (!detectedRegions.length) {
    regionList.innerHTML = '<div class="empty-state">No text detected in this image.</div>';
    return;
  }
  for (const region of detectedRegions) {
    const row = document.createElement("label");
    row.className = "region-row";
    const include = document.createElement("input");
    include.type = "checkbox";
    include.checked = true;
    include.className = "region-enabled";
    const text = document.createElement("span");
    text.className = "region-text";
    text.textContent = region.text || "(no recognized text)";
    const score = document.createElement("small");
    score.textContent = region.confidence == null ? "—" : `${Math.round(region.confidence * 100)}%`;
    row.append(include, text, score);
    row.dataset.regionIndex = String(region.index);
    regionList.append(row);
  }
}

cleanButton.addEventListener("click", async () => {
  if (!selectedFile || !detectedRegions.length) return;
  cleanButton.disabled = true;
  ocrMessage.textContent = "Removing selected text with OpenCV inpainting…";
  try {
    const selected = [...regionList.querySelectorAll(".region-row")]
      .filter(row => row.querySelector(".region-enabled").checked)
      .map(row => detectedRegions[Number(row.dataset.regionIndex)]);
    if (!selected.length) throw new Error("Select at least one detected text region.");
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("regions_json", JSON.stringify(selected));
    const response = await fetch(window.comicTranslator.apiBaseUrl + "/api/v1/images/clean-preview", { method: "POST", body });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.detail || "Image cleanup failed");
    }
    const blob = await response.blob();
    if (cleanedObjectUrl) URL.revokeObjectURL(cleanedObjectUrl);
    cleanedObjectUrl = URL.createObjectURL(blob);
    previewImage.src = cleanedObjectUrl;
    downloadCleaned.href = cleanedObjectUrl;
    downloadCleaned.hidden = false;
    ocrMessage.textContent = "Cleanup preview ready. The original image has not been changed.";
  } catch (error) {
    ocrMessage.textContent = error.message;
  } finally {
    cleanButton.disabled = false;
  }
});

checkLocalEngine();
