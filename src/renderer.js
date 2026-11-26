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
let detectedGroups = [];
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
  projectList.innerHTML = "";
  if (!result.projects.length) {
    projectList.innerHTML = '<div class="empty-state">No projects yet. Create your first comic project to get started.</div>';
    return;
  }
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
    const actions = document.createElement("div");
    actions.className = "project-row-actions";
    const open = document.createElement("button");
    open.className = "primary-button project-open-button";
    open.textContent = "Open";
    open.addEventListener("click", () => openProject(project));
    const remove = document.createElement("button");
    remove.className = "danger-button";
    remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      const confirmed = window.confirm(
        'Delete "' + project.name + '"?\\n\\nThis permanently removes the project, its downloaded pages, processed images, exports and saved history from this computer.'
      );
      if (!confirmed) return;
      remove.disabled = true;
      remove.textContent = "Deleting…";
      try {
        const response = await fetch(window.comicTranslator.apiBaseUrl + "/api/v1/projects/" + encodeURIComponent(project.id), { method: "DELETE" });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || "Could not delete project");
        if (selectedProject?.id === project.id) {
          selectedProject = null;
          window.__comicSelectedProject = null;
          window.__comicSelectedProjectId = null;
          workspace.hidden = true;
          document.getElementById("pipeline-workbench").hidden = true;
        }
        await loadProjects();
      } catch (error) {
        window.alert(error.message);
        remove.disabled = false;
        remove.textContent = "Delete";
      }
    });
    actions.append(open, remove);
    card.append(details, date, actions);
    projectList.append(card);
  }
}

function openProject(project) {
  selectedProject = project;
  window.__comicSelectedProject = project;
  window.__comicSelectedProjectId = project.id;
  document.getElementById("pipeline-workbench").hidden = false;
  workspaceTitle.textContent = project.name;
  workspace.hidden = true;
  workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  if (window.comicPipeline) window.comicPipeline.reload().catch(error => console.error(error));
}

function resetOcrResults() {
  detectedRegions = [];
  detectedGroups = [];
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
  document.getElementById("pipeline-workbench").hidden = true;
  selectedProject = null;
  window.__comicSelectedProject = null;
  window.__comicSelectedProjectId = null;
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
    source_url: data.get("source_url") || ""
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
  ocrMessage.textContent = "PP-OCR ကို CPU ပေါ်မှာ စတင်ပြီး စာသားတွေကို ရှာဖွေနေသည်။ ပထမဆုံးအကြိမ်မှာ OCR model ကို download လုပ်နိုင်သည်။";
  try {
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("language", selectedProject.source_language || "English");
    const response = await fetch(window.comicTranslator.apiBaseUrl + "/api/v1/images/ocr-preview", { method: "POST", body });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "OCR request failed");
    detectedRegions = result.regions;
    const groupedResponse = await fetch(window.comicTranslator.apiBaseUrl + "/api/v1/images/group-regions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regions: detectedRegions })
    });
    const grouped = await groupedResponse.json();
    if (!groupedResponse.ok) throw new Error(grouped.detail || "Could not group OCR text lines");
    detectedGroups = grouped.groups;
    renderRegions();
    ocrMessage.textContent = `${result.model} က စာသား ${result.count} ခု ရှာတွေ့ပြီး ${grouped.count} blocks အဖြစ် စုစည်းထားသည်။ ${result.width} × ${result.height} ပုံဖြစ်သည်။ Cleanup မလုပ်ခင် တစ်ခုချင်းစီ စစ်ဆေး/ပြင်ဆင်နိုင်သည်။`;
    cleanButton.disabled = detectedGroups.length === 0;
  } catch (error) {
    ocrMessage.textContent = error.message;
  } finally {
    detectButton.disabled = !selectedFile;
  }
});

function renderRegions() {
  regionCount.textContent = String(detectedGroups.length);
  regionList.innerHTML = "";
  if (!detectedGroups.length) {
    regionList.innerHTML = '<div class="empty-state">No text detected in this image.</div>';
    return;
  }
  for (const group of detectedGroups) {
    const card = document.createElement("article");
    card.className = "region-card";
    card.dataset.groupIndex = String(group.group_index);
    const header = document.createElement("label");
    header.className = "region-select";
    const include = document.createElement("input");
    include.type = "checkbox";
    include.checked = true;
    include.className = "region-enabled";
    const heading = document.createElement("strong");
    heading.textContent = `Text block ${group.group_index + 1} · ${group.line_count} line(s)`;
    header.append(include, heading);
    const text = document.createElement("textarea");
    text.className = "region-edit-text";
    text.value = group.text;
    text.rows = Math.min(5, Math.max(2, group.line_count));
    const geometry = document.createElement("div");
    geometry.className = "region-geometry";
    for (const [key, label] of [["x","X"],["y","Y"],["width","W"],["height","H"]]) {
      const field = document.createElement("label");
      field.textContent = label;
      const input = document.createElement("input");
      input.type = "number";
      input.min = key === "width" || key === "height" ? "1" : "0";
      input.step = "1";
      input.value = String(group[key]);
      input.dataset.geometry = key;
      field.append(input);
      geometry.append(field);
    }
    const confidence = document.createElement("small");
    confidence.className = "region-confidence";
    confidence.textContent = group.confidence == null ? "Confidence unavailable" : `AI confidence: ${Math.round(group.confidence * 100)}%`;
    card.append(header, text, geometry, confidence);
    regionList.append(card);
  }
}

function getEditedGroupGeometry(card, group) {
  const edited = { ...group };
  for (const input of card.querySelectorAll("[data-geometry]")) {
    const key = input.dataset.geometry;
    const value = Number(input.value);
    if (!Number.isInteger(value) || (key === "width" || key === "height" ? value <= 0 : value < 0)) {
      throw new Error("Text block coordinates must be non-negative whole numbers; width/height must be positive.");
    }
    edited[key] = value;
  }
  if (edited.x + edited.width > previewImage.naturalWidth || edited.y + edited.height > previewImage.naturalHeight) {
    throw new Error("A text block extends outside the image. Adjust X/Y/width/height.");
  }
  return edited;
}

function buildLineMasks(group, editedGroup) {
  const scaleX = editedGroup.width / Math.max(1, group.width);
  const scaleY = editedGroup.height / Math.max(1, group.height);
  const dx = editedGroup.x - group.x;
  const dy = editedGroup.y - group.y;
  return group.region_indices.map(index => detectedRegions[index]).filter(Boolean).map(line => {
    const relativeX = line.x - group.x;
    const relativeY = line.y - group.y;
    return {
      x: Math.round(editedGroup.x + relativeX * scaleX),
      y: Math.round(editedGroup.y + relativeY * scaleY),
      width: Math.max(1, Math.round(line.width * scaleX)),
      height: Math.max(1, Math.round(line.height * scaleY))
    };
  });
}

cleanButton.addEventListener("click", async () => {
  if (!selectedFile || !detectedRegions.length) return;
  cleanButton.disabled = true;
  const selectedModel = document.getElementById("preview-inpainting-model").value;
  ocrMessage.textContent = "AI inpainting with " + (selectedModel === "aot_gan" ? "AOT-GAN" : "LaMa Manga") + "…";
  try {
    const selected = [...regionList.querySelectorAll(".region-card")]
      .filter(card => card.querySelector(".region-enabled").checked)
      .map(card => {
        const group = detectedGroups[Number(card.dataset.groupIndex)];
        const editedGroup = getEditedGroupGeometry(card, group);
        const maskRegions = buildLineMasks(group, editedGroup);
        return {
          ...editedGroup,
          text: card.querySelector(".region-edit-text").value,
          mask_regions: maskRegions.length ? maskRegions : [editedGroup]
        };
      });
    if (!selected.length) throw new Error("Select at least one text block.");
    const body = new FormData();
    body.append("file", selectedFile);
    body.append("regions_json", JSON.stringify(selected));
    body.append("model", selectedModel);
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
    ocrMessage.textContent = "AI inpainting preview ready (" + (selectedModel === "aot_gan" ? "AOT-GAN" : "LaMa Manga") + "). Original image is unchanged.";
  } catch (error) {
    ocrMessage.textContent = error.message;
  } finally {
    cleanButton.disabled = false;
  }
});

checkLocalEngine();
