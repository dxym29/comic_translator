const statusText = document.getElementById("service-status");
const statusDot = document.querySelector(".status-dot");

async function checkLocalEngine() {
  try {
    const health = await window.comicTranslator.getHealth();
    statusText.textContent = health.status === "ok" ? "Local engine connected" : "Local engine unavailable";
    statusDot.classList.toggle("online", health.status === "ok");
  } catch {
    statusText.textContent = "Waiting for local engine";
    statusDot.classList.remove("online");
  }
}

checkLocalEngine();
