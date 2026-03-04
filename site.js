const PYODIDE_INDEX_URL = "https://cdn.jsdelivr.net/pyodide/v0.28.2/full/";
const ASSET_VERSION = "20260304-4";

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
  noticeText: document.getElementById("noticeText"),
  headlineText: document.getElementById("headlineText"),
  headlineSubtext: document.getElementById("headlineSubtext"),
  summaryPills: document.getElementById("summaryPills"),
  metricCredits: document.getElementById("metricCredits"),
  metricGpa: document.getElementById("metricGpa"),
  metricDeficit: document.getElementById("metricDeficit"),
  metricCourses: document.getElementById("metricCourses"),
  deficitShowcase: document.getElementById("deficitShowcase"),
  warningList: document.getElementById("warningList"),
  termTableBody: document.getElementById("termTableBody"),
  courseTableBody: document.getElementById("courseTableBody"),
  completionViz: document.getElementById("completionViz"),
  requirementGroups: document.getElementById("requirementGroups"),
  overflowSummary: document.getElementById("overflowSummary"),
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
  els.engineStatus.className = `engine-chip ${kind}`;
  const icon = kind === "ready" ? "✅" : kind === "error" ? "❌" : "⏳";
  els.engineStatus.textContent = `${icon} ${title}`;
  els.engineDetail.textContent = detail;
}

function setImportDock(open) {
  els.importDockBody.classList.toggle("is-open", open);
  els.toggleImportDock.textContent = open ? "入力欄をたたむ" : "入力欄を開く";
  els.toggleImportDock.setAttribute("aria-expanded", open ? "true" : "false");
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

function buildRequirementGroupMarkup(group, index) {
  const fillClass = categoryFillClasses[index % categoryFillClasses.length];
  const percent = Math.round(clamp(Number(group.percent || 0), 0, 1) * 100);
  const tone = group.status === "達成" ? "ok" : "warn";
  const metaText =
    group.status === "達成"
      ? "大区分は充足済み"
      : group.items.length
        ? `未充足 ${escapeHtml(group.unmet_item_count)} 件`
        : `残り ${escapeHtml(group.deficit)} 単位`;
  const itemsMarkup = group.items.length
    ? group.items
        .map((item) => {
          const itemTone = item.status === "達成" ? "ok" : "warn";
          const itemPercent = Math.round(clamp(Number(item.percent || 0), 0, 1) * 100);
          const noteMarkup = item.rule_messages.length
            ? `
                <ul class="detail-note-list">
                  ${item.rule_messages.map((message) => `<li>${escapeHtml(message)}</li>`).join("")}
                </ul>
              `
            : item.deficit > 0
              ? `<div class="detail-note">あと ${escapeHtml(item.deficit)} 単位不足</div>`
              : "";

          return `
            <div class="detail-subrow ${item.status !== "達成" ? "is-deficit" : ""}">
              <div class="detail-subhead">
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(item.earned)} / ${escapeHtml(item.required)} 単位</span>
              </div>
              <div class="bar-track thin-track">
                <div class="bar-fill ${fillClass}" style="width:${itemPercent}%"></div>
              </div>
              <span class="status-chip ${itemTone}">${escapeHtml(item.status)}</span>
              ${noteMarkup}
            </div>
          `;
        })
        .join("")
    : group.sources.length
      ? group.sources
          .map((source) => {
            const sourcePercent = Math.round(
              clamp(Number(source.credits || 0) / Math.max(Number(group.required || 0), 1), 0, 1) * 100,
            );
            return `
              <div class="detail-subrow">
                <div class="detail-subhead">
                  <strong>${escapeHtml(source.label)}</strong>
                  <span>${escapeHtml(source.credits)} 単位</span>
                </div>
                <div class="bar-track thin-track">
                  <div class="bar-fill ${fillClass}" style="width:${sourcePercent}%"></div>
                </div>
                <span class="status-chip ok">算入中</span>
              </div>
            `;
          })
          .join("")
      : '<div class="empty-cell">内訳はありません。</div>';

  return `
    <article class="detail-category-card ${group.status !== "達成" ? "is-deficit" : ""}">
      <div class="detail-card-head">
        <div>
          <h3>${escapeHtml(group.name)}</h3>
          <p>${escapeHtml(group.earned)} / ${escapeHtml(group.required)} 単位</p>
        </div>
        <div class="detail-head-side">
          <span class="detail-percent">${percent}%</span>
          <span class="status-chip ${tone}">${escapeHtml(group.status)}</span>
        </div>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${fillClass}" style="width:${percent}%"></div>
      </div>
      <div class="detail-card-meta">
        <span>${metaText}</span>
        <span>${escapeHtml(group.raw_earned)} 単位入力済み</span>
      </div>
      <div class="detail-subgrid">
        ${itemsMarkup}
      </div>
    </article>
  `;
}

function renderRequirementGroups(target, groups) {
  if (!groups.length) {
    target.innerHTML = '<div class="empty-cell">データ取込後に表示されます。</div>';
    return;
  }

  target.innerHTML = groups.map((group, index) => buildRequirementGroupMarkup(group, index)).join("");
}

function buildRequirementGroupsFromProgressRows(progressRows, freeElectiveSources = []) {
  if (!Array.isArray(progressRows) || !progressRows.length) {
    return [];
  }

  const groupRows = progressRows.filter((row) => row?.name === "合計");
  return groupRows.map((groupRow) => {
    const items = progressRows
      .filter((row) => row?.group === groupRow.group && row?.name !== "合計")
      .map((row) => {
        const earned = Number(row.earned || 0);
        const required = Number(row.required || 0);
        const deficit = Math.max(required - earned, 0);
        return {
          id: row.name,
          name: row.name,
          earned,
          required,
          raw_earned: earned,
          deficit,
          percent: required > 0 ? Math.min(earned / required, 1) : 0,
          status: row.status || (deficit > 0 ? "不足" : "達成"),
          rule_messages: [],
        };
      });

    const earned = Number(groupRow.earned || 0);
    const required = Number(groupRow.required || 0);
    const deficit = Math.max(required - earned, 0);
    const unresolvedItems = items.filter((item) => item.status !== "達成").length;

    return {
      id: groupRow.group,
      name: groupRow.group,
      earned,
      required,
      raw_earned: earned,
      deficit,
      percent: required > 0 ? Math.min(earned / required, 1) : 0,
      status: groupRow.status || (deficit > 0 || unresolvedItems > 0 ? "不足" : "達成"),
      unmet_item_count: unresolvedItems,
      items,
      sources: items.length ? [] : freeElectiveSources,
    };
  });
}

function renderDeficitShowcase(cards) {
  if (!cards.length) {
    els.deficitShowcase.innerHTML = `
      <article class="deficit-card is-clear">
        <div class="deficit-card-head">
          <div>
            <span class="deficit-kicker">Clear</span>
            <h3>不足要件はありません</h3>
          </div>
          <span class="status-chip ok">達成</span>
        </div>
        <p class="deficit-summary">この時点では卒業要件の不足表示は出ていません。</p>
      </article>
    `;
    return;
  }

  els.deficitShowcase.innerHTML = cards
    .map(
      (card) => `
        <article class="deficit-card">
          <div class="deficit-card-head">
            <div>
              <span class="deficit-kicker">Deficit</span>
              <h3>${escapeHtml(card.title)}</h3>
            </div>
            <strong>${escapeHtml(card.value)}</strong>
          </div>
          <ul class="deficit-points">
            ${card.lines.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function buildDeficitCardsFromDeficits(deficits, summary) {
  if (!Array.isArray(deficits) || !deficits.length) {
    return [];
  }

  const cards = [];
  const totalLine = deficits.find((line) => String(line).startsWith("総単位数:"));
  if (totalLine) {
    cards.push({
      title: "総単位",
      value: `あと ${summary.deficit} 単位`,
      tone: "warn",
      lines: [totalLine],
    });
  }

  const detailLines = deficits.filter((line) => line !== totalLine);
  for (const line of detailLines) {
    const separatorIndex = String(line).indexOf(":");
    const title = separatorIndex >= 0 ? String(line).slice(0, separatorIndex).trim() : "不足要件";
    const body = separatorIndex >= 0 ? String(line).slice(separatorIndex + 1).trim() : String(line);
    cards.push({
      title,
      value: body,
      tone: "warn",
      lines: [line],
    });
  }

  return cards;
}

function renderOverflowSummary(overflowItems, freeElectiveSources) {
  const items = freeElectiveSources.length
    ? freeElectiveSources
    : overflowItems.map((item) => {
        const [label, credits] = String(item).split(":");
        return { label: label?.trim() || item, credits: credits?.trim() || "" };
      });

  if (!items.length) {
    els.overflowSummary.innerHTML = '<div class="empty-cell">自由選択に算入された余剰はありません。</div>';
    return;
  }

  els.overflowSummary.innerHTML = items
    .map(
      (item) => `
        <div class="overflow-card">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.credits)}${typeof item.credits === "number" ? " 単位" : ""}</strong>
        </div>
      `,
    )
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
  /* Hero donut removed in compact layout – now handled by renderCompletionViz */
}

function renderCompletionViz(summary, deficitCount, warningCount) {
  const earned = Number(summary.total_earned || 0);
  const total = 130;
  const percent = clamp(earned / total, 0, 1);

  els.completionViz.innerHTML = `
    <div class="donut-layout">
      <div class="donut-center">
        ${buildDonutSvg(percent, "sun", 212, 18)}
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

function renderSummaryPills(summary, requirementGroups, warnings) {
  const totalGroups = requirementGroups.length || 4;
  const achievedGroups = requirementGroups.filter((group) => group.status === "達成").length;
  const pills = [
    `総不足 ${summary.deficit} 単位`,
    `大区分 ${achievedGroups} / ${totalGroups} 達成`,
    `警告 ${warnings.length} 件`,
  ];
  els.summaryPills.innerHTML = pills.map((pill) => `<span class="summary-pill">${escapeHtml(pill)}</span>`).join("");
}

function renderPayload(payload) {
  appState = payload.state;

  const summary = payload.summary;
  const warningItems = payload.warnings || [];
  const freeElectiveSources = payload.free_elective_sources || [];
  const requirementGroups =
    payload.requirement_groups?.length
      ? payload.requirement_groups
      : buildRequirementGroupsFromProgressRows(payload.progress_rows || [], freeElectiveSources);
  const deficitCards =
    payload.deficit_cards?.length
      ? payload.deficit_cards
      : buildDeficitCardsFromDeficits(payload.deficits || [], summary);

  els.noticeText.textContent = payload.notice || "待機中です。";
  els.metricCredits.textContent = `${summary.total_earned} / 130`;
  els.metricGpa.textContent = formatMaybeNumber(summary.gpa);
  els.metricDeficit.textContent = String(summary.deficit);
  els.metricCourses.textContent = String(appState.courses.length);
  els.headlineText.textContent = summary.message;
  els.headlineSubtext.textContent = `データソース: ${appState.source || "blank"} / GPA対象単位: ${summary.gpa_credits}`;
  els.exportJson.value = payload.json_text;

  renderSummaryPills(summary, requirementGroups, warningItems);
  renderHeroDonut(summary, payload.deficits.length, warningItems.length);
  renderCompletionViz(summary, payload.deficits.length, warningItems.length);
  renderRequirementGroups(els.requirementGroups, requirementGroups);
  renderDeficitShowcase(deficitCards);
  renderOverflowSummary(payload.overflow || [], freeElectiveSources);
  renderGpaCharts(payload.term_rows);

  renderList(els.warningList, warningItems, "警告はありません。");
  renderTermRows(payload.term_rows);
  renderCourseRows(payload.course_rows);
}

async function loadPythonModules() {
  const files = ["requirements.py", "simulator.py", "browser_bridge.py"];
  for (const file of files) {
    const response = await fetch(`./${file}?v=${ASSET_VERSION}`, { cache: "no-store" });
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

setImportDock(true);
initialize();
