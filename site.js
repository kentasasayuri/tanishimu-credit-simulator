const PYODIDE_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v0.28.2/full/";

const KOAN_HEADER_SAMPLE =
  "No.\t科目詳細区分\t科目小区分\t科目名\tリーディング\t高度教養\t単位数\t修得年度\t修得学期\t評語\t合否\n";

let pyodide = null;
let appState = {
  student_name: "",
  enrollment_year: 2025,
  courses: [],
  source: "blank",
};

const els = {
  koanText: document.getElementById("koanText"),
  jsonText: document.getElementById("jsonText"),
  exportJson: document.getElementById("exportJson"),
  koanImportButton: document.getElementById("koanImportButton"),
  jsonImportButton: document.getElementById("jsonImportButton"),
  clearButton: document.getElementById("clearButton"),
  copyJsonButton: document.getElementById("copyJsonButton"),
  downloadJsonButton: document.getElementById("downloadJsonButton"),
  sampleHeaderButton: document.getElementById("sampleHeaderButton"),
  engineStatus: document.getElementById("engineStatus"),
  engineDetail: document.getElementById("engineDetail"),
  noticeText: document.getElementById("noticeText"),
  headlineCard: document.querySelector(".headline-card"),
  headlineText: document.getElementById("headlineText"),
  headlineSubtext: document.getElementById("headlineSubtext"),
  metricCredits: document.getElementById("metricCredits"),
  metricGpa: document.getElementById("metricGpa"),
  metricDeficit: document.getElementById("metricDeficit"),
  metricCourses: document.getElementById("metricCourses"),
  deficitList: document.getElementById("deficitList"),
  warningList: document.getElementById("warningList"),
  progressTableBody: document.getElementById("progressTableBody"),
  termTableBody: document.getElementById("termTableBody"),
  courseTableBody: document.getElementById("courseTableBody"),
  inputTabs: [...document.querySelectorAll(".panel-tab")],
  inputPanels: [...document.querySelectorAll(".input-panel")],
  resultTabs: [...document.querySelectorAll(".result-tab")],
  resultPanels: [...document.querySelectorAll(".result-panel")],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatMaybeNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const number = Number(value);
  if (Number.isInteger(number)) {
    return String(number);
  }
  return number.toFixed(2);
}

function setButtonsDisabled(disabled) {
  [
    els.koanImportButton,
    els.jsonImportButton,
    els.clearButton,
    els.copyJsonButton,
    els.downloadJsonButton,
    els.sampleHeaderButton,
  ].forEach((button) => {
    button.disabled = disabled;
  });
}

function currentMode() {
  const selected = document.querySelector('input[name="importMode"]:checked');
  return selected ? selected.value : "replace";
}

function setEngineState(kind, title, detail) {
  els.engineStatus.className = `engine-status ${kind}`;
  els.engineStatus.textContent = title;
  els.engineDetail.textContent = detail;
}

function activateTab(buttons, panels, targetId) {
  buttons.forEach((button) => {
    const isActive = button.dataset.panelTarget === targetId || button.dataset.resultTarget === targetId;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  panels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === targetId);
  });
}

function renderList(target, items, emptyText) {
  if (!items.length) {
    target.classList.add("empty");
    target.innerHTML = `<li>${escapeHtml(emptyText)}</li>`;
    return;
  }
  target.classList.remove("empty");
  target.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderProgressRows(rows) {
  if (!rows.length) {
    els.progressTableBody.innerHTML =
      '<tr><td colspan="5" class="empty-cell">データ取込後に表示されます。</td></tr>';
    return;
  }

  els.progressTableBody.innerHTML = rows
    .map((row) => {
      const tone = row.status === "達成" ? "ok" : "warn";
      return `
        <tr>
          <td>${escapeHtml(row.group)}</td>
          <td>${escapeHtml(row.name)}</td>
          <td>${escapeHtml(row.earned)}</td>
          <td>${escapeHtml(row.required)}</td>
          <td><span class="status-chip ${tone}">${escapeHtml(row.status)}</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderTermRows(rows) {
  if (!rows.length) {
    els.termTableBody.innerHTML =
      '<tr><td colspan="5" class="empty-cell">データ取込後に表示されます。</td></tr>';
    return;
  }

  els.termTableBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.term)}</td>
          <td>${escapeHtml(formatMaybeNumber(row.term_gpa))}</td>
          <td>${escapeHtml(formatMaybeNumber(row.cumulative_gpa))}</td>
          <td>${escapeHtml(row.credits)}</td>
          <td>${escapeHtml(row.course_count)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderCourseRows(rows) {
  if (!rows.length) {
    els.courseTableBody.innerHTML =
      '<tr><td colspan="6" class="empty-cell">データ取込後に表示されます。</td></tr>';
    return;
  }

  els.courseTableBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.year)}</td>
          <td>${escapeHtml(row.semester)}</td>
          <td>${escapeHtml(row.name)}</td>
          <td>${escapeHtml(row.category)}</td>
          <td>${escapeHtml(row.credits)}</td>
          <td>${escapeHtml(row.grade)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderPayload(payload) {
  appState = payload.state;

  const summary = payload.summary;
  els.noticeText.textContent = payload.notice || "待機中です。";
  els.metricCredits.textContent = `${summary.total_earned} / 130`;
  els.metricGpa.textContent = formatMaybeNumber(summary.gpa);
  els.metricDeficit.textContent = String(summary.deficit);
  els.metricCourses.textContent = String(appState.courses.length);
  els.headlineText.textContent = summary.message;
  els.headlineSubtext.textContent = `データソース: ${appState.source || "blank"} / GPA対象単位: ${summary.gpa_credits}`;
  els.headlineCard.classList.remove("ok", "warn", "risk");
  if (summary.tone && summary.tone !== "idle") {
    els.headlineCard.classList.add(summary.tone);
  }
  els.exportJson.value = payload.json_text;

  const warningItems = [...payload.warnings, ...payload.overflow];
  renderList(els.deficitList, payload.deficits, "不足要件はありません。");
  renderList(els.warningList, warningItems, "警告はありません。");
  renderProgressRows(payload.progress_rows);
  renderTermRows(payload.term_rows);
  renderCourseRows(payload.course_rows);
}

async function loadPythonModules() {
  const files = ["requirements.py", "simulator.py", "browser_bridge.py"];
  for (const file of files) {
    const response = await fetch(`./${file}`);
    if (!response.ok) {
      throw new Error(`${file} の取得に失敗しました。`);
    }
    const source = await response.text();
    pyodide.FS.writeFile(file, source, { encoding: "utf8" });
  }

  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, ".")
import browser_bridge
`);
}

async function callPython(functionName, kwargs = {}) {
  pyodide.globals.set("bridge_kwargs", JSON.stringify(kwargs));
  const responseText = await pyodide.runPythonAsync(`
import json
from browser_bridge import ${functionName}
payload = json.loads(bridge_kwargs)
${functionName}(**payload)
`);
  return JSON.parse(responseText);
}

async function renderInitialState() {
  const payload = await callPython("render_state", { state_json: JSON.stringify(appState) });
  renderPayload(payload);
}

async function handleKoanImport() {
  const text = els.koanText.value.trim();
  if (!text) {
    els.noticeText.textContent = "KOAN テキストを貼り付けてください。";
    return;
  }

  setButtonsDisabled(true);
  try {
    const payload = await callPython("import_koan_state", {
      state_json: JSON.stringify(appState),
      koan_text: text,
      mode: currentMode(),
    });
    renderPayload(payload);
    activateTab(els.resultTabs, els.resultPanels, "overviewPanel");
  } catch (error) {
    els.noticeText.textContent = `読込失敗: ${error.message}`;
  } finally {
    setButtonsDisabled(false);
  }
}

async function handleJsonImport() {
  const text = els.jsonText.value.trim();
  if (!text) {
    els.noticeText.textContent = "JSON を貼り付けてください。";
    return;
  }

  setButtonsDisabled(true);
  try {
    const payload = await callPython("import_json_state", {
      state_json: JSON.stringify(appState),
      json_text: text,
      mode: currentMode(),
    });
    renderPayload(payload);
    activateTab(els.resultTabs, els.resultPanels, "overviewPanel");
  } catch (error) {
    els.noticeText.textContent = `読込失敗: ${error.message}`;
  } finally {
    setButtonsDisabled(false);
  }
}

async function handleClear() {
  setButtonsDisabled(true);
  try {
    const payload = await callPython("clear_state");
    els.koanText.value = "";
    els.jsonText.value = "";
    renderPayload(payload);
    activateTab(els.resultTabs, els.resultPanels, "overviewPanel");
  } catch (error) {
    els.noticeText.textContent = `初期化失敗: ${error.message}`;
  } finally {
    setButtonsDisabled(false);
  }
}

function insertSampleHeader() {
  if (!els.koanText.value.trim()) {
    els.koanText.value = KOAN_HEADER_SAMPLE;
  } else if (!els.koanText.value.includes("科目詳細区分")) {
    els.koanText.value = `${KOAN_HEADER_SAMPLE}${els.koanText.value}`;
  }
  els.koanText.focus();
  els.noticeText.textContent = "KOAN の見本ヘッダーを入力欄に入れました。";
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText(els.exportJson.value);
    els.noticeText.textContent = "現在の JSON をクリップボードにコピーしました。";
  } catch {
    els.noticeText.textContent = "JSON のコピーに失敗しました。";
  }
}

function downloadJson() {
  const blob = new Blob([els.exportJson.value], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "tanishimu-data.json";
  anchor.click();
  URL.revokeObjectURL(url);
  els.noticeText.textContent = "JSON を保存しました。";
}

async function initialize() {
  setButtonsDisabled(true);
  setEngineState("loading", "Booting", "Pyodide と判定ロジックをロードしています。");

  try {
    pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });
    await loadPythonModules();
    await renderInitialState();
    setEngineState("ready", "Ready", "ブラウザ内だけで計算します。KOAN テキストを貼り付けてください。");
  } catch (error) {
    setEngineState("error", "Failed", error.message);
    els.noticeText.textContent = `初期化失敗: ${error.message}`;
  } finally {
    setButtonsDisabled(false);
  }
}

els.inputTabs.forEach((button) => {
  button.addEventListener("click", () => activateTab(els.inputTabs, els.inputPanels, button.dataset.panelTarget));
});

els.resultTabs.forEach((button) => {
  button.addEventListener("click", () =>
    activateTab(els.resultTabs, els.resultPanels, button.dataset.resultTarget),
  );
});

els.koanImportButton.addEventListener("click", handleKoanImport);
els.jsonImportButton.addEventListener("click", handleJsonImport);
els.clearButton.addEventListener("click", handleClear);
els.copyJsonButton.addEventListener("click", copyJson);
els.downloadJsonButton.addEventListener("click", downloadJson);
els.sampleHeaderButton.addEventListener("click", insertSampleHeader);

initialize();
