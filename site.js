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

const categoryFillClasses = ["fill-sun", "fill-cyan", "fill-mint", "fill-rose"];

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
  toggleImportDock: document.getElementById("toggleImportDock"),
  importDockBody: document.getElementById("importDockBody"),
  engineStatus: document.getElementById("engineStatus"),
  engineDetail: document.getElementById("engineDetail"),
  heroDonut: document.getElementById("heroDonut"),
  heroStatusLabel: document.getElementById("heroStatusLabel"),
  heroGpaCredits: document.getElementById("heroGpaCredits"),
  noticeText: document.getElementById("noticeText"),
  headlineCard: document.querySelector(".story-card"),
  headlineText: document.getElementById("headlineText"),
  headlineSubtext: document.getElementById("headlineSubtext"),
  summaryPills: document.getElementById("summaryPills"),
  metricCredits: document.getElementById("metricCredits"),
  metricGpa: document.getElementById("metricGpa"),
  metricDeficit: document.getElementById("metricDeficit"),
  metricCourses: document.getElementById("metricCourses"),
  deficitList: document.getElementById("deficitList"),
  warningList: document.getElementById("warningList"),
  progressTableBody: document.getElementById("progressTableBody"),
  termTableBody: document.getElementById("termTableBody"),
  courseTableBody: document.getElementById("courseTableBody"),
  completionViz: document.getElementById("completionViz"),
  categoryBars: document.getElementById("categoryBars"),
  categoryDetails: document.getElementById("categoryDetails"),
  overviewGpaTrend: document.getElementById("overviewGpaTrend"),
  gpaTrendLarge: document.getElementById("gpaTrendLarge"),
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

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
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

function setImportDock(open) {
  els.importDockBody.classList.toggle("is-open", open);
  els.toggleImportDock.textContent = open ? "入力を閉じる" : "入力を開く";
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

function buildDonutSvg(percent, accent = "sun", size = 220, stroke = 18) {
  const safePercent = clamp(percent, 0, 1);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = circumference * safePercent;
  const gradientId = `grad-${accent}-${Math.random().toString(36).slice(2, 8)}`;

  const stops =
    accent === "cyan"
      ? ['<stop offset="0%" stop-color="#67d8ff" />', '<stop offset="100%" stop-color="#8cf0bf" />']
      : accent === "mint"
        ? ['<stop offset="0%" stop-color="#8cf0bf" />', '<stop offset="100%" stop-color="#67d8ff" />']
        : ['<stop offset="0%" stop-color="#ffc978" />', '<stop offset="100%" stop-color="#ff9f87" />'];

  return `
    <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" aria-hidden="true">
      <defs>
        <linearGradient id="${gradientId}" x1="0%" y1="0%" x2="100%" y2="100%">
          ${stops.join("")}
        </linearGradient>
      </defs>
      <circle cx="${size / 2}" cy="${size / 2}" r="${radius}" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="${stroke}" />
      <circle
        cx="${size / 2}"
        cy="${size / 2}"
        r="${radius}"
        fill="none"
        stroke="url(#${gradientId})"
        stroke-width="${stroke}"
        stroke-linecap="round"
        stroke-dasharray="${dash} ${circumference - dash}"
        transform="rotate(-90 ${size / 2} ${size / 2})"
      />
    </svg>
  `;
}

function renderHeroDonut(summary, deficitCount, warningCount) {
  const earned = Number(summary.total_earned || 0);
  const percent = clamp(earned / 130, 0, 1);
  const statusText =
    summary.tone === "ok"
      ? "卒業圏内"
      : summary.tone === "risk"
        ? "条件未充足"
        : summary.tone === "warn"
          ? "要件不足"
          : "待機中";

  els.heroDonut.innerHTML = `
    <div class="donut-layout">
      <div class="donut-center">
        ${buildDonutSvg(percent, "sun", 220, 18)}
      </div>
      <div class="donut-legend">
        <div class="donut-legend-row">
          <span>取得単位</span>
          <strong>${earned} / 130</strong>
        </div>
        <div class="donut-legend-row">
          <span>不足要件</span>
          <strong>${deficitCount} 件</strong>
        </div>
        <div class="donut-legend-row">
          <span>警告</span>
          <strong>${warningCount} 件</strong>
        </div>
      </div>
    </div>
  `;

  els.heroStatusLabel.textContent = statusText;
  els.heroGpaCredits.textContent = String(summary.gpa_credits ?? 0);
}

function renderCompletionViz(summary, deficitCount, warningCount) {
  const earned = Number(summary.total_earned || 0);
  const total = 130;
  const percent = clamp(earned / total, 0, 1);

  els.completionViz.innerHTML = `
    <div class="donut-layout">
      <div class="donut-center">
        ${buildDonutSvg(percent, "sun", 250, 20)}
      </div>
      <div class="donut-legend">
        <div class="donut-legend-row">
          <span>到達率</span>
          <strong>${Math.round(percent * 100)}%</strong>
        </div>
        <div class="donut-legend-row">
          <span>残り単位</span>
          <strong>${summary.deficit}</strong>
        </div>
        <div class="donut-legend-row">
          <span>不足要件</span>
          <strong>${deficitCount} 件</strong>
        </div>
        <div class="donut-legend-row">
          <span>警告</span>
          <strong>${warningCount} 件</strong>
        </div>
      </div>
    </div>
  `;
}

function renderCategoryBars(progressRows) {
  const topLevelRows = progressRows.filter((row) => row.name === "合計");
  if (!topLevelRows.length) {
    els.categoryBars.innerHTML = '<div class="empty-cell">データ取込後に表示されます。</div>';
    return;
  }

  els.categoryBars.innerHTML = topLevelRows
    .map((row, index) => {
      const percent = row.required > 0 ? clamp(row.earned / row.required, 0, 1) : 0;
      const fillClass = categoryFillClasses[index % categoryFillClasses.length];
      return `
        <div class="bar-row">
          <div class="bar-label-row">
            <strong>${escapeHtml(row.group)}</strong>
            <span>${escapeHtml(row.earned)} / ${escapeHtml(row.required)}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill ${fillClass}" style="width:${percent * 100}%"></div>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderCategoryDetails(progressRows, freeElectiveSources = []) {
  const topLevelRows = progressRows.filter((row) => row.name === "合計");
  if (!topLevelRows.length) {
    els.categoryDetails.innerHTML = '<div class="empty-cell">データ取込後に表示されます。</div>';
    return;
  }

  const cards = topLevelRows.map((row, index) => {
    const children = progressRows.filter((child) => child.group === row.group && child.name !== "合計");
    const percent = row.required > 0 ? clamp(row.earned / row.required, 0, 1) : 0;
    const fillClass = categoryFillClasses[index % categoryFillClasses.length];
    const sourceMarkup =
      !children.length && freeElectiveSources.length
        ? freeElectiveSources
            .map((source) => {
              const sourcePercent = clamp(source.credits / Math.max(row.required, 1), 0, 1);
              return `
                <div class="detail-subrow">
                  <div class="detail-subhead">
                    <strong>${escapeHtml(source.label)}</strong>
                    <span>${escapeHtml(source.credits)} 単位</span>
                  </div>
                  <div class="bar-track thin-track">
                    <div class="bar-fill ${fillClass}" style="width:${sourcePercent * 100}%"></div>
                  </div>
                </div>
              `;
            })
            .join("")
        : "";

    const childMarkup = children.length
      ? children
          .map((child) => {
            const childPercent = child.required > 0 ? clamp(child.earned / child.required, 0, 1) : 0;
            const childTone = child.status === "達成" ? "ok" : "warn";
            return `
              <div class="detail-subrow">
                <div class="detail-subhead">
                  <strong>${escapeHtml(child.name)}</strong>
                  <span>${escapeHtml(child.earned)} / ${escapeHtml(child.required)}</span>
                </div>
                <div class="bar-track thin-track">
                  <div class="bar-fill ${fillClass}" style="width:${childPercent * 100}%"></div>
                </div>
                <span class="status-chip ${childTone}">${escapeHtml(child.status)}</span>
              </div>
            `;
          })
          .join("")
      : sourceMarkup || '<div class="empty-cell">内訳はありません。</div>';

    return `
      <article class="detail-category-card">
        <div class="detail-card-head">
          <div>
            <h3>${escapeHtml(row.group)}</h3>
            <p>${escapeHtml(row.earned)} / ${escapeHtml(row.required)} 単位</p>
          </div>
          <span class="detail-percent">${Math.round(percent * 100)}%</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill ${fillClass}" style="width:${percent * 100}%"></div>
        </div>
        <div class="detail-subgrid">
          ${childMarkup}
        </div>
      </article>
    `;
  });

  els.categoryDetails.innerHTML = cards.join("");
}

function buildLineChart(rows, { width, height, accent }) {
  if (!rows.length) {
    return `
      <div class="line-chart-shell">
        <div class="empty-cell">GPA 対象科目を読み込むと表示されます。</div>
      </div>
    `;
  }

  const paddingX = 26;
  const paddingTop = 22;
  const paddingBottom = 28;
  const plotWidth = width - paddingX * 2;
  const plotHeight = height - paddingTop - paddingBottom;
  const maxY = 4;

  const points = rows.map((row, index) => {
    const x = rows.length === 1 ? width / 2 : paddingX + (plotWidth * index) / (rows.length - 1);
    const y = paddingTop + plotHeight - (clamp(Number(row.term_gpa || 0), 0, maxY) / maxY) * plotHeight;
    return { x, y, label: row.term, value: Number(row.term_gpa || 0) };
  });

  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const areaPath = `${path} L ${points[points.length - 1].x} ${height - paddingBottom} L ${points[0].x} ${height - paddingBottom} Z`;
  const latest = rows[rows.length - 1];
  const highest = rows.reduce((acc, row) => Math.max(acc, Number(row.term_gpa || 0)), 0);

  const gradientId = `line-grad-${accent}-${Math.random().toString(36).slice(2, 8)}`;
  const accentStops =
    accent === "mint"
      ? ['<stop offset="0%" stop-color="#8cf0bf" />', '<stop offset="100%" stop-color="#67d8ff" />']
      : ['<stop offset="0%" stop-color="#67d8ff" />', '<stop offset="100%" stop-color="#ffc978" />'];

  const pointsMarkup = points
    .map(
      (point) => `
        <circle cx="${point.x}" cy="${point.y}" r="4.5" fill="#091521" stroke="url(#${gradientId})" stroke-width="3" />
      `,
    )
    .join("");

  const labelsMarkup = points
    .map(
      (point) => `
        <text x="${point.x}" y="${height - 6}" text-anchor="middle" fill="rgba(239,247,251,0.58)" font-size="11">
          ${escapeHtml(point.label)}
        </text>
      `,
    )
    .join("");

  return `
    <div class="line-chart-shell">
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" aria-hidden="true">
        <defs>
          <linearGradient id="${gradientId}" x1="0%" y1="0%" x2="100%" y2="0%">
            ${accentStops.join("")}
          </linearGradient>
          <linearGradient id="${gradientId}-area" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="rgba(103,216,255,0.28)" />
            <stop offset="100%" stop-color="rgba(103,216,255,0.02)" />
          </linearGradient>
        </defs>
        <line x1="${paddingX}" y1="${paddingTop}" x2="${paddingX}" y2="${height - paddingBottom}" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
        <line x1="${paddingX}" y1="${height - paddingBottom}" x2="${width - paddingX}" y2="${height - paddingBottom}" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
        <path d="${areaPath}" fill="url(#${gradientId}-area)" />
        <path d="${path}" fill="none" stroke="url(#${gradientId})" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        ${pointsMarkup}
        ${labelsMarkup}
      </svg>
      <div class="line-chart-note">
        <div>
          <span>直近学期</span>
          <strong>${escapeHtml(latest.term)}</strong>
        </div>
        <div>
          <span>最高期別 GPA</span>
          <strong>${formatMaybeNumber(highest)}</strong>
        </div>
      </div>
    </div>
  `;
}

function renderGpaCharts(termRows) {
  els.overviewGpaTrend.innerHTML = buildLineChart(termRows, { width: 360, height: 220, accent: "cyan" });
  els.gpaTrendLarge.innerHTML = buildLineChart(termRows, { width: 720, height: 300, accent: "mint" });
}

function renderSummaryPills(summary, deficits, warnings) {
  const pills = [
    `総不足 ${summary.deficit} 単位`,
    `不足要件 ${deficits.length} 件`,
    `警告 ${warnings.length} 件`,
  ];
  els.summaryPills.innerHTML = pills.map((pill) => `<span class="summary-pill">${escapeHtml(pill)}</span>`).join("");
}

function renderPayload(payload) {
  appState = payload.state;

  const summary = payload.summary;
  const warningItems = payload.warnings || [];

  els.noticeText.textContent = payload.notice || "待機中です。";
  els.metricCredits.textContent = `${summary.total_earned} / 130`;
  els.metricGpa.textContent = formatMaybeNumber(summary.gpa);
  els.metricDeficit.textContent = String(summary.deficit);
  els.metricCourses.textContent = String(appState.courses.length);
  els.headlineText.textContent = summary.message;
  els.headlineSubtext.textContent = `データソース: ${appState.source || "blank"} / GPA対象単位: ${summary.gpa_credits}`;
  els.exportJson.value = payload.json_text;

  renderSummaryPills(summary, payload.deficits, warningItems);
  renderHeroDonut(summary, payload.deficits.length, warningItems.length);
  renderCompletionViz(summary, payload.deficits.length, warningItems.length);
  renderCategoryBars(payload.progress_rows);
  renderCategoryDetails(payload.progress_rows, payload.free_elective_sources || []);
  renderGpaCharts(payload.term_rows);

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
    setImportDock(false);
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
    setImportDock(false);
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
    setImportDock(true);
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
  setImportDock(true);
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

els.toggleImportDock.addEventListener("click", () => {
  setImportDock(!els.importDockBody.classList.contains("is-open"));
});

els.koanImportButton.addEventListener("click", handleKoanImport);
els.jsonImportButton.addEventListener("click", handleJsonImport);
els.clearButton.addEventListener("click", handleClear);
els.copyJsonButton.addEventListener("click", copyJson);
els.downloadJsonButton.addEventListener("click", downloadJson);
els.sampleHeaderButton.addEventListener("click", insertSampleHeader);

setImportDock(false);
initialize();
