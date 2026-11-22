(() => {
  const names = ["fetch", "extract", "remove", "translate", "typeset", "export"];
  const labels = ["Fetch images", "Ollama text extraction", "LaMa AI text removal", "Gemini translation", "Myanmar typesetting", "CBZ / ZIP export"];
  const $ = (id) => document.getElementById(id);
  const list = $("pipeline-stage-list");
  if (!list) return;
  let current = "fetch";
  let history = {};
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
  function showCurrent() {
    const item = history[current] || {};
    $("pipeline-input").value = json(item.input || defaultInput(current));
    $("pipeline-output").value = json(item.output || {});
    renderStages(history);
  }
  function defaultInput(stage) {
    if (stage === "fetch") return { url: (window.__comicSelectedProject && window.__comicSelectedProject.source_url) || "" };
    if (stage === "extract") {
      const pages = history.fetch?.output?.pages || [];
      return { image_path: pages[0]?.image_path || "" };
    }
    if (stage === "remove") return {
      image_path: history.extract?.output?.image_path || "",
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
  async function autoRun() {
    if (running) return;
    running = true; paused = false; stopRequested = false;
    $("pipeline-auto").disabled = true;
    $("pipeline-pause").disabled = false;
    try {
      for (let i = names.indexOf(current); i < names.length; i++) {
        while (paused && !stopRequested) await new Promise(resolve => setTimeout(resolve, 250));
        if (stopRequested) break;
        current = names[i];
        $("pipeline-input").value = json(defaultInput(current));
        showCurrent();
        message("Auto mode: " + labels[i] + " လုပ်ဆောင်နေသည်…");
        try { await runStage(current); }
        catch (error) { message(error.message, true); throw error; }
        if (i < names.length - 1) {
          current = names[i + 1];
          $("pipeline-input").value = json(defaultInput(current));
          $("pipeline-output").value = "{}";
          renderStages(history);
        }
      }
      if (!stopRequested) message("Auto mode ပြီးပါပြီ။ Completed stages ကို ပြန်စစ်နိုင်ပါတယ်။");
    } catch (error) {
      message("ရပ်သွားသည်: " + error.message, true);
    } finally {
      running = false; paused = false;
      $("pipeline-auto").disabled = false;
      $("pipeline-pause").disabled = true;
      $("pipeline-pause").textContent = "Pause";
    }
  }
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
  $("pipeline-chapter").addEventListener("change", () => reload().catch(e => message(e.message, true)));
  window.comicPipeline = { reload, selectStage };
  renderStages();
})();
