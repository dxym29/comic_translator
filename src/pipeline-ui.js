(() => {
  const names = ["extract", "remove", "translate", "typeset", "export"];
  const labels = ["စာသားရှာဖွေခြင်း", "မူရင်းစာသားဖယ်ရှားခြင်း", "မြန်မာဘာသာပြန်ခြင်း", "မြန်မာစာထည့်ခြင်း", "ဖိုင်ထုတ်ခြင်း"];
  const $ = id => document.getElementById(id);
  const list = $("pipeline-stage-list");
  if (!list) return;

  let current = "extract";
  let history = {};
  let importRecord = null;
  let pages = [];
  let pageIndex = 0;
  let running = false;
  let paused = false;
  let stopRequested = false;
  let renderedPages = [];
  const chapter = () => $("pipeline-chapter").value.trim() || "chapter-1";
  const projectId = () => window.__comicSelectedProjectId;
  const api = window.comicTranslator.apiBaseUrl;
  const pageChapter = index => chapter() + "::page-" + String(index + 1).padStart(5, "0");
  const page = () => pages[pageIndex] || null;
  const statusNames = { pending: "မစရသေး", completed: "ပြီးပါပြီ", reviewed: "ပြင်ဆင်ပြီး", failed: "အမှားရှိ" };

  function json(value) { return JSON.stringify(value ?? {}, null, 2); }
  function parseEditor(id) {
    try { return JSON.parse($(id).value || "{}"); }
    catch { throw new Error("JSON ပုံစံ မမှန်ပါ။"); }
  }
  function message(text, error = false) {
    $("pipeline-message").textContent = text;
    $("pipeline-message").style.color = error ? "#e0a18e" : "#a8aeb9";
    $("process-status").textContent = text;
  }
  function progress(done, total, status, stage, pageNo) {
    const percent = total ? Math.min(100, Math.round(done / total * 100)) : 0;
    $("process-progress").style.width = percent + "%";
    $("process-percent").textContent = percent + "%";
    $("process-status").textContent = status;
    $("process-step").textContent = "အဆင့် — " + (stage || "မစရသေး");
    $("process-page").textContent = "စာမျက်နှာ " + (pageNo || (pages.length ? pageIndex + 1 : "—")) + " / " + (pages.length || "—");
  }
  async function request(path, options = {}) {
    const response = await fetch(api + path, {
      ...options,
      headers: { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) }
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "လုပ်ဆောင်မှု မအောင်မြင်ပါ။");
    return body;
  }
  async function loadImport() {
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline?chapter_id=" + encodeURIComponent(chapter()));
    const record = (result.stages || []).find(item => item.name === "import");
    importRecord = record && record.output?.pages?.length ? record : null;
    pages = importRecord?.output?.pages || [];
    if (pageIndex >= pages.length) pageIndex = Math.max(0, pages.length - 1);
    updatePageNavigation();
  }
  async function loadPageHistory() {
    history = {};
    if (!page()) return;
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline?chapter_id=" + encodeURIComponent(pageChapter(pageIndex)));
    for (const item of result.stages || []) history[item.name] = item;
  }
  function renderStages() {
    list.innerHTML = "";
    names.forEach((stage, index) => {
      const item = history[stage] || {};
      const button = document.createElement("button");
      button.className = "pipeline-stage" + (stage === current ? " active" : "");
      const status = item.status || "pending";
      button.innerHTML = '<span class="pipeline-stage-number">' + String(index + 1).padStart(2, "0") +
        '</span><span class="pipeline-stage-title"></span><small class="pipeline-stage-status"></small>';
      button.querySelector(".pipeline-stage-title").textContent = labels[index];
      button.querySelector(".pipeline-stage-status").textContent = statusNames[status] || status;
      button.dataset.status = status;
      button.disabled = running;
      button.addEventListener("click", () => selectStage(stage));
      list.append(button);
    });
  }
  function imagePath(value) {
    if (!value || typeof value !== "object") return "";
    return value.image_path || value.cleaned_image_path || value.pages?.[0]?.image_path || "";
  }
  async function setPreview(imageId, emptyId, path, emptyText) {
    const image = $(imageId);
    const empty = $(emptyId);
    const requestId = String(Number(image.dataset.previewRequest || 0) + 1);
    image.dataset.previewRequest = requestId;
    if (!path || !projectId()) {
      image.hidden = true;
      image.removeAttribute("src");
      if (image.dataset.previewObjectUrl) URL.revokeObjectURL(image.dataset.previewObjectUrl);
      image.dataset.previewObjectUrl = "";
      empty.hidden = false;
      empty.textContent = emptyText;
      return;
    }
    empty.hidden = false;
    empty.textContent = "ပုံ Preview ကို ဖွင့်နေသည်…";
    try {
      const url = api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
        "/image?path=" + encodeURIComponent(path) + "&v=" + Date.now();
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || ("HTTP " + response.status));
      }
      const blob = await response.blob();
      if (image.dataset.previewRequest !== requestId) return;
      const objectUrl = URL.createObjectURL(blob);
      if (image.dataset.previewObjectUrl) URL.revokeObjectURL(image.dataset.previewObjectUrl);
      image.dataset.previewObjectUrl = objectUrl;
      image.src = objectUrl;
      image.hidden = false;
      empty.hidden = true;
    } catch (error) {
      if (image.dataset.previewRequest !== requestId) return;
      image.hidden = true;
      empty.hidden = false;
      empty.textContent = "Preview မဖွင့်နိုင်ပါ — " + error.message;
    }
  }
  function updatePreviews() {
    let input = {}, output = {};
    try { input = parseEditor("pipeline-input"); } catch {}
    try { output = parseEditor("pipeline-output"); } catch {}
    const source = page()?.image_path || "";
    const inPath = imagePath(input) || source;
    let outPath = imagePath(output);
    if (!outPath && ["translate", "extract"].includes(current)) outPath = imagePath(history.remove?.output) || source;
    if (!outPath && current === "remove") outPath = source;
    setPreview("pipeline-input-image", "pipeline-input-empty", inPath, "မူရင်းစာမျက်နှာ ပုံမရှိသေးပါ");
    setPreview("pipeline-output-image", "pipeline-output-empty", outPath, "ဒီအဆင့်ရဲ့ ရလဒ် မရှိသေးပါ");
  }
  function defaultInput(stage) {
    const source = page()?.image_path || "";
    if (stage === "extract") return { image_path: source };
    if (stage === "remove") return {
      image_path: history.extract?.output?.image_path || source,
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
        image_path: history.remove?.output?.image_path || history.extract?.output?.image_path || source,
        regions: regions.map((r, i) => ({ ...r, translated_text: byId.get(String(r.id || i + 1)) || "" })),
        font_family: window.__comicSelectedProject?.font_family || "Noto Sans Myanmar",
        style: window.__comicSelectedProject?.typesetting_style || "original_bubble"
      };
    }
    return {};
  }
  async function exportInput() {
    const outputs = [];
    for (let i = 0; i < pages.length; i++) {
      const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
        "/pipeline?chapter_id=" + encodeURIComponent(pageChapter(i)));
      const typeset = (result.stages || []).find(item => item.name === "typeset");
      const path = typeset?.output?.image_path;
      if (path) outputs.push({ index: outputs.length + 1, image_path: path });
    }
    return {
      title: importRecord?.output?.title || window.__comicSelectedProject?.name || "Comic Chapter",
      chapter_number: chapter(),
      format: importRecord?.output?.source_type === "epub" ? "epub" : "zip",
      pages: outputs
    };
  }
  async function prepareStage(stage) {
    if (stage === "export") return await exportInput();
    const saved = history[stage];
    // Reuse a successful/reviewed run, but rebuild failed/pending inputs from
    // the latest upstream output so a failed attempt cannot poison retries.
    if (saved && ["completed", "reviewed"].includes(saved.status)) return saved.input || defaultInput(stage);
    return defaultInput(stage);
  }
  function showCurrent() {
    const item = history[current] || {};
    if (current !== "export") {
      const reusable = item.status && ["completed", "reviewed"].includes(item.status);
      $("pipeline-input").value = json(reusable ? (item.input || defaultInput(current)) : defaultInput(current));
    }
    $("pipeline-output").value = json(item.output || {});
    const model = $("inpainting-model");
    if (model) {
      model.closest("label").hidden = current !== "remove";
      model.value = (item.input || {}).model || "lama_manga";
    }
    renderStages();
    updatePreviews();
    updatePageNavigation();
  }
  async function selectStage(stage) {
    current = stage;
    if (stage === "export") $("pipeline-input").value = json(await exportInput());
    else $("pipeline-input").value = json(await prepareStage(stage));
    $("pipeline-output").value = json(history[stage]?.output || {});
    showCurrent();
    progress(0, 0, labels[names.indexOf(stage)] + " ကို ရွေးထားသည်။", labels[names.indexOf(stage)], null);
  }
  function updatePageNavigation() {
    $("page-counter").textContent = pages.length ? "စာမျက်နှာ " + (pageIndex + 1) + " / " + pages.length : "စာမျက်နှာ မရှိသေးပါ";
    $("page-file-name").textContent = page()?.filename || page()?.source_member || (pages.length ? "Imported comic page" : "EPUB / ZIP / Images ကို Import လုပ်ပါ");
    $("page-previous").disabled = running || pageIndex <= 0;
    $("page-next").disabled = running || pageIndex >= pages.length - 1;
    $("pipeline-auto").disabled = running || !pages.length;
    $("pipeline-run").disabled = running || !page();
    $("pipeline-save").disabled = running || !page();
    $("pipeline-next").disabled = running || !page() || current === "export";
  }
  async function reload() {
    if (!projectId()) return;
    pageIndex = 0;
    await loadImport();
    if (page()) await loadPageHistory();
    current = "extract";
    showCurrent();
    progress(0, 0, pages.length ? "Import ပြီးပါပြီ။ Auto Run သို့မဟုတ် Manual ကိုရွေးပါ။" : "EPUB / ZIP / ပုံဖိုင် Import လုပ်ပါ။", "မစရသေး", null);
  }
  function showExportLink(output) {
    const link = $("export-download");
    if (!output?.file_path) { link.hidden = true; return; }
    link.href = api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/export-file?path=" + encodeURIComponent(output.file_path);
    link.hidden = false;
    link.textContent = (output.format || "ဖိုင်") + " · " + (output.page_count || pages.length) + " မျက်နှာ Download";
  }
  async function runStage(stage = current, options = {}) {
    const input = options.input || parseEditor("pipeline-input");
    const chapterId = stage === "export" ? chapter() : pageChapter(pageIndex);
    const stageLabel = labels[names.indexOf(stage)];
    if (!options.silent) {
      message("လုပ်ဆောင်နေသည် — " + stageLabel + "…");
      progress(options.done || 0, options.total || 1, "လုပ်ဆောင်နေသည် — " + stageLabel + "…", stageLabel, pageIndex + 1);
    }
    $("pipeline-input").value = json(input);
    updatePreviews();
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline/" + stage + "/run?chapter_id=" + encodeURIComponent(chapterId), {
        method: "POST", body: JSON.stringify({ input })
      });
    if (stage !== "export") history[stage] = result.run;
    $("pipeline-input").value = json(input);
    $("pipeline-output").value = json(result.run.output);
    if (stage === "export") showExportLink(result.run.output);
    updatePreviews();
    renderStages();
    if (!options.silent) message(stageLabel + " ပြီးပါပြီ။");
    return result.run.output;
  }
  async function saveOutput() {
    const output = parseEditor("pipeline-output");
    const editChapter = current === "export" ? chapter() : pageChapter(pageIndex);
    const result = await request("/api/v1/projects/" + encodeURIComponent(projectId()) +
      "/pipeline/" + current + "/output?chapter_id=" + encodeURIComponent(editChapter), {
        method: "PUT", body: JSON.stringify({ output })
      });
    history[current] = result.run;
    renderStages();
    updatePreviews();
    message("ပြင်ဆင်ထားတဲ့ ရလဒ်ကို သိမ်းပြီးပါပြီ။");
  }
  async function waitIfPaused() {
    while (paused && !stopRequested) await new Promise(resolve => setTimeout(resolve, 200));
    if (stopRequested) throw new Error("ရပ်တန့်ရန် တောင်းဆိုထားသည်။");
  }
  async function autoRun() {
    if (running || !pages.length) return;
    running = true; paused = false; stopRequested = false;
    renderedPages = [];
    $("pipeline-auto").disabled = true;
    $("pipeline-pause").disabled = false;
    $("pipeline-stop").disabled = false;
    updatePageNavigation();
    const steps = ["extract", "remove", "translate", "typeset"];
    const total = pages.length * steps.length + 1;
    let done = 0;
    try {
      for (let p = 0; p < pages.length; p++) {
        await waitIfPaused();
        pageIndex = p;
        await loadPageHistory();
        current = "extract";
        for (const stage of steps) {
          await waitIfPaused();
          current = stage;
          const stageLabel = labels[names.indexOf(stage)];
          showCurrent();
          progress(done, total, "စာမျက်နှာ " + (p + 1) + "/" + pages.length + " — " + stageLabel + " လုပ်နေသည်…", stageLabel, p + 1);
          const input = defaultInput(stage);
          const output = await runStage(stage, { input, silent: true, done, total });
          done++;
          progress(done, total, "စာမျက်နှာ " + (p + 1) + "/" + pages.length + " — " + stageLabel + " ပြီးပါပြီ။", stageLabel, p + 1);
          if (stage === "typeset" && output.image_path) renderedPages.push({ index: p + 1, image_path: output.image_path });
        }
      }
      await waitIfPaused();
      current = "export";
      const input = await exportInput();
      if (!input.pages.length) throw new Error("ထုတ်ရန် Typeset ပြီးသော စာမျက်နှာ မရှိပါ။");
      $("pipeline-input").value = json(input);
      $("pipeline-output").value = "{}";
      showCurrent();
      progress(done, total, "နောက်ဆုံးဖိုင်ကို Export လုပ်နေသည်…", labels[4], pages.length);
      const output = await runStage("export", { input, silent: true });
      done++;
      progress(total, total, "အားလုံးပြီးပါပြီ။ " + output.page_count + " မျက်နှာ Export လုပ်ပြီးပါပြီ။", "ပြီးဆုံး", pages.length);
      message("လုပ်ငန်းစဉ် အောင်မြင်စွာ ပြီးဆုံးပါပြီ။");
    } catch (error) {
      message(stopRequested ? "လုပ်ငန်းစဉ်ကို ရပ်ထားပါတယ်။ ပြီးပြီးသားစာမျက်နှာတွေကို သိမ်းထားပါတယ်။" : "လုပ်ဆောင်မှု မအောင်မြင်ပါ — " + error.message, !stopRequested);
    } finally {
      running = false; paused = false; stopRequested = false;
      $("pipeline-pause").disabled = true;
      $("pipeline-stop").disabled = true;
      $("pipeline-pause").textContent = "Pause";
      await loadPageHistory().catch(() => {});
      showCurrent();
      updatePageNavigation();
    }
  }
  async function importFiles(input, kind) {
    const files = [...(input.files || [])];
    if (!files.length || !projectId()) return;
    input.disabled = true;
    message("ဖိုင်တွေကို Import လုပ်နေပါတယ်…");
    progress(0, 1, "ဖိုင်တွေကို Import လုပ်နေပါတယ်…", "Import", 0);
    try {
      const body = new FormData();
      const endpoint = kind === "images" ? "import-images" : "import-" + kind;
      if (kind === "images") files.forEach(file => body.append("files", file));
      else body.append("file", files[0]);
      const response = await fetch(api + "/api/v1/projects/" + encodeURIComponent(projectId()) +
        "/" + endpoint + "?chapter_id=" + encodeURIComponent(chapter()), { method: "POST", body });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || "Import မအောင်မြင်ပါ။");
      importRecord = result.run;
      pages = result.import.pages || [];
      pageIndex = 0;
      history = {};
      current = "extract";
      await loadPageHistory();
      showCurrent();
      progress(1, 1, "Import ပြီးပါပြီ။ အလိုအလျောက် မစပါ။ Auto Run သို့မဟုတ် Manual ကိုရွေးပါ။", "Import ပြီး", 1);
      message("Import အောင်မြင်ပါတယ်။ စာမျက်နှာ " + pages.length + " ခု ရပါပြီ။ အခုမှ စတင်ရန် ရွေးချယ်နိုင်ပါတယ်။");
    } catch (error) {
      message("Import မအောင်မြင်ပါ — " + error.message, true);
    } finally {
      input.disabled = false;
      input.value = "";
      updatePageNavigation();
    }
  }
  async function changePage(delta) {
    if (running || !pages.length) return;
    pageIndex = Math.max(0, Math.min(pages.length - 1, pageIndex + delta));
    await loadPageHistory();
    showCurrent();
    message("စာမျက်နှာ " + (pageIndex + 1) + " ကို ပြထားပါတယ်။");
  }

  $("epub-import-file").addEventListener("change", event => importFiles(event.target, "epub"));
  $("zip-import-file").addEventListener("change", event => importFiles(event.target, "zip"));
  $("images-import-file").addEventListener("change", event => importFiles(event.target, "images"));
  $("page-previous").addEventListener("click", () => changePage(-1).catch(error => message(error.message, true)));
  $("page-next").addEventListener("click", () => changePage(1).catch(error => message(error.message, true)));
  $("pipeline-run").addEventListener("click", async () => {
    try {
      // Respect the visible editor: manual corrections must not be overwritten
      // by prepareStage when the user presses Run.
      const input = current === "export" ? await exportInput() : parseEditor("pipeline-input");
      await runStage(current, { input });
    } catch (error) { message("အဆင့် မအောင်မြင်ပါ — " + error.message, true); }
  });
  $("pipeline-save").addEventListener("click", () => saveOutput().catch(error => message(error.message, true)));
  $("pipeline-next").addEventListener("click", () => {
    const index = names.indexOf(current);
    if (index < names.length - 1) selectStage(names[index + 1]).catch(error => message(error.message, true));
  });
  $("pipeline-auto").addEventListener("click", autoRun);
  $("pipeline-pause").addEventListener("click", () => {
    if (!running) return;
    paused = !paused;
    $("pipeline-pause").textContent = paused ? "ဆက်လုပ်ရန်" : "ခဏရပ်";
    message(paused ? "လက်ရှိအဆင့်ပြီးတာနဲ့ ခဏရပ်စောင့်ပါမယ်။" : "လုပ်ငန်းစဉ် ပြန်စနေပါတယ်။");
  });
  $("pipeline-stop").addEventListener("click", () => {
    if (!running) return;
    stopRequested = true;
    paused = false;
    message("လက်ရှိလုပ်ဆောင်နေတဲ့ အဆင့်ပြီးတာနဲ့ ရပ်ပါမယ်။");
  });
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
  window.comicPipeline = { reload, selectStage, changePage };
  renderStages();
})();
