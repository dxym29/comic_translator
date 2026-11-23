(() => {
  const names = ["fetch", "extract", "remove", "translate", "typeset", "export"];
  const labels = ["Fetch images", "Ollama text extraction", "LaMa AI text removal", "Gemini translation", "Myanmar typesetting", "CBZ / ZIP export"];
  const $ = (id) => document.getElementById(id);
  const list = $("pipeline-stage-list");
  if (!list) return;
  let current = "fetch";
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
    catch { throw new Error("JSON format မမှန်ပါ။ Input/Output ကို စစ်ပါ။"); }
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
  function showCurrent() {
    const item = history[current] || {};
    $("pipeline-input").value = json(item.input || defaultInput(current));
    $("pipeline-output").value = json(item.output || {});
    renderStages(history);
    updatePreviews();
  }
  function defaultInput(stage) {
    if (stage === "fetch") return { url: (window.__comicSelectedProject && window.__comicSelectedProject.source_url) || "" };
    if (stage === "extract") {
      const pages = history.fetch?.output?.pages || [];
      return { image_path: activePage?.image_path || pages[0]?.image_path || "" };
    }
    if (stage === "remove") return {
      image_path: activePage?.image_path || history.extract?.output?.image_path || "",
      regions: history.extract?.output?.regions || []
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
      return { title: window.__comicSelectedProject?.name || "Comic Chapter",
        chapter_number: chapter(), pages: imagePath ? [{ index: 1, image_path: imagePath }] : [] };
    }
    return {};
  }
  function selectStage(stage) {
    current = stage;
    showCurrent();
    message("Selected: " + labels[names.indexOf(stage)] + ". Input/Output ကို စစ်ပြီး Run သို့မဟုတ် Save လုပ်ပါ။");
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
    updatePreviews();
    renderStages(history);
    message(labels[names.indexOf(stage)] + " ပြီးပါပြီ။ Output ကိုစစ်ပြီး နောက်တစ်ဆင့်ဆက်နိုင်ပါတယ်။");
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
    message("Manual output ကို သိမ်းပြီးပါပြီ။ နောက် stage မှာ ဒီ output ကို အသုံးပြုနိုင်ပါတယ်။");
  }
  async function waitIfPaused() {
    while (paused && !stopRequested) await new Promise(resolve => setTimeout(resolve, 250));
    if (stopRequested) throw new Error("Paused by user");
  }
  async function autoRun() {
    if (running) return;
    running = true; paused = false; stopRequested = false; renderedPages = [];
    $("pipeline-auto").disabled = true;
    $("pipeline-pause").disabled = false;
    try {
      if (current === "fetch" || !history.fetch?.output?.pages?.length) {
        current = "fetch";
        $("pipeline-input").value = json(defaultInput("fetch"));
        showCurrent();
        message("Auto mode: chapter ပုံများ ရယူနေသည်…");
        const fetched = await runStage("fetch");
        history.fetch = { ...(history.fetch || {}), output: fetched };
      }
      const pages = history.fetch?.output?.pages || [];
      if (!pages.length) throw new Error("Fetch output ထဲမှာ pages မရှိပါ။");
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
      $("pipeline-input").value = json({
        title: window.__comicSelectedProject?.name || "Comic Chapter",
        chapter_number: chapter(), pages: renderedPages
      });
      showCurrent();
      message("CBZ export လုပ်ဆောင်နေသည်…");
      await runStage("export");
      message("Auto batch ပြီးပါပြီ။ " + renderedPages.length + " pages ကို export လုပ်ပြီးပါပြီ။");
    } catch (error) {
      if (stopRequested) message("Pause လုပ်ထားသည်။ ပြီးပြီးသား stage များကို သိမ်းထားပြီး နောက်မှ ပြန်စနိုင်သည်။");
      else message("ရပ်သွားသည်: " + error.message, true);
    } finally {
      running = false; paused = false; activePage = null;
      $("pipeline-auto").disabled = false;
      $("pipeline-pause").disabled = true;
      $("pipeline-pause").textContent = "Pause";
    }
  }
  $("epub-import-file").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file || !projectId()) return;
    const button = event.target;
    button.disabled = true;
    message("EPUB ဖိုင်ကို စစ်ဆေးပြီး Manga စာမျက်နှာများ ထုတ်ယူနေသည်…");
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch(api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
        "/import-epub?chapter_id=" + encodeURIComponent(chapter()), {
          method: "POST", body
        });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "EPUB import failed");
      await reload();
      selectStage("extract");
      message("EPUB Import အောင်မြင်ပါပြီ။ " + result.import.count +
        " pages ထုတ်ယူပြီးပါပြီ။ Auto run ဖြင့် Extract ကနေ ဆက်လုပ်နိုင်ပါတယ်။");
    } catch (error) {
      message(error.message, true);
    } finally {
      button.disabled = false;
      event.target.value = "";
    }
  });
  $("pipeline-run").addEventListener("click", async () => {
    try { await runStage(); } catch (e) { message(e.message, true); }
  });
  $("pipeline-save").addEventListener("click", async () => {
    try { await saveOutput(); } catch (e) { message(e.message, true); }
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
    message(paused ? "Pause requested. လက်ရှိ stage ပြီးတာနဲ့ ရပ်စောင့်မယ်။" : "Resume လုပ်ပြီး ဆက်လက်လုပ်ဆောင်နေသည်။");
  });
  $("pipeline-refresh").addEventListener("click", () => reload().catch(e => message(e.message, true)));
  $("pipeline-input").addEventListener("input", updatePreviews);
  $("pipeline-output").addEventListener("input", updatePreviews);
  $("pipeline-chapter").addEventListener("change", () => reload().catch(e => message(e.message, true)));
  window.comicPipeline = { reload, selectStage };
  renderStages();
})();
