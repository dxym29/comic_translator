const statusText = document.getElementById("service-status");
const statusDot = document.querySelector(".status-dot");
const projectList = document.getElementById("project-list");
const createButton = document.getElementById("create-project");
const dialog = document.getElementById("project-dialog");
const form = document.getElementById("project-form");
const message = document.getElementById("form-message");

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
    const title = document.createElement("strong");
    title.textContent = project.name;
    const details = document.createElement("span");
    details.textContent = `${project.source_language} → ${project.target_language} · ${project.typesetting_style === "professional" ? "Professional Typesetting" : "Original Bubble Style"}`;
    const date = document.createElement("small");
    date.textContent = new Date(project.updated_at).toLocaleString();
    card.append(title, details, date);
    projectList.append(card);
  }
}

createButton.addEventListener("click", () => {
  message.textContent = "";
  dialog.showModal();
});

document.getElementById("cancel-project").addEventListener("click", () => dialog.close());

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

checkLocalEngine();
