(() => {
  const names = ["import", "extract", "remove", "translate", "typeset", "export"];
  const labels = ["Import files", "Detect text", "Remove original text", "Translate", "Myanmar lettering", "Export"];
  const $ = id => document.getElementById(id);
  const list = $("pipeline-stage-list");
  if (!list) return;
  let current = "extract";
  let history = {};
  let activePage = null;
  let renderedPages = [];
  let running = false;
  let paused = false;
  let stopRequested = false;
  const chapter = () => $("pipeline-chapter").value.trim() || "chapter-1";
  const projectId = () => window.__comicSelectedProjectId;
  const api = window.comicTranslator.apiBaseUrl;

  function json(value) { return JSON.stringify(value ?? {}, null, 2); }
  function parseEditor(id) {
    try { return JSON.parse($(id).value || "{}"); }
    catch { throw new Error("JSON format မမှန်ပါ။"); }
  }
  function message(text, error = false) {
    $("pipeline-message").textContent = text;
    $("pipeline-message").style.color = error ? "#e0a18e" : "#a8aeb9";
  }
  async function request(path, options = {}) {
    const response = await fetch(api + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Pipeline request failed");
    return body;
  }
  function renderStages(state = {}) {
    list.innerHTML = "";
    for (const [i, stage] of names.entries()) {
      const item = state[stage] || {};
      const button = document.createElement("button");
      button.className = "pipeline-stage" + (stage === current ? " active" : "");
      const status = item.status || "pending";
      button.innerHTML = '<span class="pipeline-stage-number">' + String(i + 1).padStart(2, "0") +
        '</span><span class="pipeline-stage-title"></span><small class="pipeline-stage-status"></small>';
      button.querySelector(".pipeline-stage-title").textContent = labels[i];
      button.querySelector(".pipeline-stage-status").textContent = status;
      button.dataset.status = status;
      button.addEventListener("click", () => selectStage(stage));
      list.append(button);
    }
  }
  function previewImage(elementId, data) {
    const image = $(elementId);
    let path = "";
    try {
      const value = typeof data === "string" ? JSON.parse(data || "{}") : data;
      path = value.image_path || value.pages?.[0]?.image_path || "";
    } catch {}
    if (!path || !projectId()) { image.hidden = true; image.removeAttribute("src"); return; }
    image.src = api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/image?path=" + encodeURIComponent(path);
    image.hidden = false;
  }
  function updatePreviews() {
    previewImage("pipeline-input-image", $("pipeline-input").value);
    previewImage("pipeline-output-image", $("pipeline-output").value);
  }
  function defaultInput(stage) {
    if (stage === "import") return {};
    if (stage === "extract") {
      const pages = history.import?.output?.pages || [];
      return { image_path: activePage?.image_path || pages[0]?.image_path || "" };
    }
    if (stage === "remove") return {
      image_path: activePage?.image_path || history.extract?.output?.image_path || "",
      regions: history.extract?.output?.regions || [],
      model: $("inpainting-model")?.value || "lama_manga",
      padding_ratio: 0.18
    };
    if (stage === "translate") return {
      regions: (history.extract?.output?.regions || []).map((r, i) => ({ ...r, id: r.id || String(i + 1) }))
    };
    if (stage === "typeset") {
      const regions = history.extract?.output?.regions || [];
      const translations = history.translate?.output?.translations || [];
      const byId = new Map(translations.map(t => [String(t.id), t.text]));
      return {
        image_path: history.remove?.output?.image_path || "",
        regions: regions.map((r, i) => ({ ...r, translated_text: byId.get(String(r.id || i + 1)) || "" })),
        font_family: window.__comicSelectedProject?.font_family || "Noto Sans Myanmar",
        style: window.__comicSelectedProject?.typesetting_style || "original_bubble"
      };
    }
    if (stage === "export") {
      const imagePath = history.typeset?.output?.image_path || "";
      const sourceType = history.import?.output?.source_type || "images";
      return {
        title: history.import?.output?.title || window.__comicSelectedProject?.name || "Comic Chapter",
        chapter_number: chapter(),
        format: sourceType === "epub" ? "epub" : "zip",
        pages: imagePath ? [{ index: 1, image_path: imagePath }] : []
      };
    }
    return {};
  }
  function showCurrent() {
    const item = history[current] || {};
    const stageInput = item.input || defaultInput(current);
    $("pipeline-input").value = json(stageInput);
    $("pipeline-output").value = json(item.output || {});
    const modelSelect = $("inpainting-model");
    if (modelSelect) modelSelect.closest("label").hidden = current !== "remove";
    if (modelSelect) modelSelect.value = stageInput.model || "lama_manga";
    renderStages(history);
    updatePreviews();
  }
  function selectStage(stage) {
    current = stage;
    showCurrent();
    message("ရွေးထားသောအဆင့် — " + labels[names.indexOf(stage)]);
  }
  async function reload() {
    if (!projectId()) return;
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline?chapter_id=" + encodeURIComponent(chapter()));
    history = {};
    for (const item of result.stages || []) history[item.name] = item;
    showCurrent();
  }
  async function runStage(stage = current) {
    const input = parseEditor("pipeline-input");
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline/" + stage + "/run?chapter_id=" + encodeURIComponent(chapter()), {
        method: "POST", body: JSON.stringify({ input })
      });
    history[stage] = result.run;
    $("pipeline-output").value = json(result.run.output);
    if (stage === "export" && result.run.output.file_path) {
      const link = $("export-download");
      link.href = api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
        "/export-file?path=" + encodeURIComponent(result.run.output.file_path);
      link.hidden = false;
      link.textContent = "Download " + (result.run.output.format || "chapter") +
        " (" + result.run.output.page_count + " pages)";
    }
    updatePreviews();
    renderStages(history);
    message(labels[names.indexOf(stage)] + " ပြီးပါပြီ။");
    return result.run.output;
  }
  async function saveOutput() {
    const output = parseEditor("pipeline-output");
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline/" + current + "/output?chapter_id=" + encodeURIComponent(chapter()), {
        method: "PUT", body: JSON.stringify({ output })
      });
    history[current] = result.run;
    renderStages(history);
    message("ပြင်ဆင်ထားသော Output ကို သိမ်းပြီးပါပြီ။");
  }
  async function waitIfPaused() {
    while (paused && !stopRequested) await new Promise(resolve => setTimeout(resolve, 250));
    if (stopRequested) throw new Error("Paused by user");
  }
  async function autoRun() {
    if (running) return;
    const pages = history.import?.output?.pages || [];
    if (!pages.length) {
      message("အရင်ဆုံး EPUB, ZIP သို့မဟုတ် ပုံဖိုင်တွေ Import လုပ်ပါ။", true);
      return;
    }
    running = true; paused = false; stopRequested = false; renderedPages = [];
    $("pipeline-auto").disabled = true;
    $("pipeline-pause").disabled = false;
    try {
      const firstStage = Math.max(1, names.indexOf(current));
      for (let p = 0; p < pages.length; p++) {
        activePage = pages[p];
        message("Page " + (p + 1) + "/" + pages.length + " ကို လုပ်ဆောင်နေသည်…");
        for (let i = firstStage; i <= 4; i++) {
          await waitIfPaused();
          current = names[i];
          $("pipeline-input").value = json(defaultInput(current));
          $("pipeline-output").value = "{}";
          showCurrent();
          message("Page " + (p + 1) + "/" + pages.length + " · " + labels[i] + "…");
          const output = await runStage(current);
          if (i === 4 && output.image_path) renderedPages.push({ index: p + 1, image_path: output.image_path });
        }
      }
      await waitIfPaused();
      current = "export";
      const sourceType = history.import?.output?.source_type || "images";
      $("pipeline-input").value = json({
        title: history.import?.output?.title || window.__comicSelectedProject?.name || "Comic Chapter",
        chapter_number: chapter(),
        format: sourceType === "epub" ? "epub" : "zip",
        pages: renderedPages
      });
      showCurrent();
      message((sourceType === "epub" ? "EPUB" : "ZIP") + " export လုပ်နေသည်…");
      await runStage("export");
      message("ပြီးပါပြီ။ " + renderedPages.length + " pages ကို " +
        (sourceType === "epub" ? "EPUB" : "ZIP") + " အဖြစ် ထုတ်ပြီးပါပြီ။");
    } catch (error) {
      if (stopRequested) message("Pause လုပ်ထားသည်။ ပြီးပြီးသားအဆင့်များကို သိမ်းထားသည်။");
      else message("ရပ်သွားသည်: " + error.message, true);
    } finally {
      running = false; paused = false; activePage = null;
      $("pipeline-auto").disabled = false;
      $("pipeline-pause").disabled = true;
      $("pipeline-pause").textContent = "Pause";
    }
  }
  async function importFiles(input, kind) {
    const files = [...(input.files || [])];
    if (!files.length || !projectId()) return;
    input.disabled = true;
    message("ဖိုင်များကို Import လုပ်နေသည်…");
    try {
      const body = new FormData();
      const endpoint = kind === "images" ? "import-images" : "import-" + kind;
      if (kind === "images") files.forEach(file => body.append("files", file));
      else body.append("file", files[0]);
      const response = await fetch(api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
        "/" + endpoint + "?chapter_id=" + encodeURIComponent(chapter()), { method: "POST", body });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "Import failed");
      history.import = result.run;
      current = "extract";
      showCurrent();
      message("Import အောင်မြင်ပါပြီ။ စာမျက်နှာ " + result.import.count +
        " ခု ထည့်ပြီးပါပြီ။ Auto Run ကိုနှိပ်ပါ။");
    } catch (error) {
      message(error.message, true);
    } finally {
      input.disabled = false;
      input.value = "";
    }
  }
  $("epub-import-file").addEventListener("change", event => importFiles(event.target, "epub"));
  $("zip-import-file").addEventListener("change", event => importFiles(event.target, "zip"));
  $("images-import-file").addEventListener("change", event => importFiles(event.target, "images"));
  $("pipeline-run").addEventListener("click", async () => {
    try { await runStage(); } catch (error) { message(error.message, true); }
  });
  $("pipeline-save").addEventListener("click", async () => {
    try { await saveOutput(); } catch (error) { message(error.message, true); }
  });
  $("pipeline-next").addEventListener("click", () => {
    const i = names.indexOf(current);
    if (i < names.length - 1) selectStage(names[i + 1]);
  });
  $("pipeline-auto").addEventListener("click", autoRun);
  $("pipeline-pause").addEventListener("click", () => {
    if (!running) return;
    paused = !paused;
    $("pipeline-pause").textContent = paused ? "Resume" : "Pause";
    message(paused ? "Pause requested. လက်ရှိအဆင့်ပြီးရင် ရပ်စောင့်မယ်။" : "ဆက်လက်လုပ်ဆောင်နေသည်။");
  });
  $("pipeline-refresh").addEventListener("click", () => reload().catch(error => message(error.message, true)));
  $("inpainting-model").addEventListener("change", () => {
    if (current !== "remove") return;
    try {
      const input = parseEditor("pipeline-input");
      input.model = $("inpainting-model").value;
      $("pipeline-input").value = json(input);
    } catch (error) { message(error.message, true); }
  });
  $("pipeline-input").addEventListener("input", updatePreviews);
  $("pipeline-output").addEventListener("input", updatePreviews);
  $("pipeline-chapter").addEventListener("change", () => reload().catch(error => message(error.message, true)));
  window.comicPipeline = { reload, selectStage };
  renderStages();
})();
