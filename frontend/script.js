/**
 * DataGenAI — Frontend Script
 * Calls backend API at API_BASE. No direct AI calls — pure HTTP to Flask.
 */

// ─── Configuration ──────────────────────────────────────────────────────────
const API_BASE = "http://localhost:5000";  // ← Change this if backend runs on a different host/port

// ─── State ──────────────────────────────────────────────────────────────────
let lastResult = null;   // Stores the full /api/generate response
let activeTable = null;  // Currently active table tab

// ─── DOM refs ────────────────────────────────────────────────────────────────
const ddlInput     = document.getElementById("ddlInput");
const editorGutter = document.getElementById("editorGutter");
const rowCount     = document.getElementById("rowCount");
const rowMinus     = document.getElementById("rowMinus");
const rowPlus      = document.getElementById("rowPlus");
const generateBtn  = document.getElementById("generateBtn");
const clearEditorBtn = document.getElementById("clearEditorBtn");
const loadExampleBtn = document.getElementById("loadExampleBtn");
const clearCacheBtn  = document.getElementById("clearCacheBtn");

const emptyState   = document.getElementById("emptyState");
const loadingState = document.getElementById("loadingState");
const errorState   = document.getElementById("errorState");
const results      = document.getElementById("results");
const errorMessage = document.getElementById("errorMessage");
const dismissError = document.getElementById("dismissError");
const loadingLabel = document.getElementById("loadingLabel");

const metaRow    = document.getElementById("metaRow");
const tokensUsed = document.getElementById("tokensUsed");
const tableCount = document.getElementById("tableCount");
const cacheHit   = document.getElementById("cacheHit");
const resultsBadge = document.getElementById("resultsBadge");

const tabBar     = document.getElementById("tabBar");
const tabContent = document.getElementById("tabContent");

const copySeedBtn = document.getElementById("copySeedBtn");
const downloadBtn = document.getElementById("downloadBtn");

const cacheLabel  = document.getElementById("cacheLabel");
const mapModal    = document.getElementById("mapModal");
const mapModalTitle = document.getElementById("mapModalTitle");
const mapModalBody  = document.getElementById("mapModalBody");
const mapModalClose = document.getElementById("mapModalClose");
const toast         = document.getElementById("toast");

// ─── Pipeline step refs ───────────────────────────────────────────────────────
const pSteps = [
  document.getElementById("pStep1"),
  document.getElementById("pStep2"),
  document.getElementById("pStep3"),
  document.getElementById("pStep4"),
];

const pipelineMessages = [
  "Parsing SQL DDL…",
  "Mapping columns via Llama 3.1…",
  "Resolving foreign key order…",
  "Generating Faker data…",
];

// ─── Example DDL ─────────────────────────────────────────────────────────────
const EXAMPLE_DDL = `CREATE TABLE users (
  id         INT PRIMARY KEY,
  first_name VARCHAR(50) NOT NULL,
  last_name  VARCHAR(50) NOT NULL,
  email      VARCHAR(255) UNIQUE NOT NULL,
  phone      VARCHAR(20),
  city       VARCHAR(100),
  country    VARCHAR(50),
  created_at TIMESTAMP NOT NULL,
  is_active  BOOLEAN
);

CREATE TABLE products (
  id          INT PRIMARY KEY,
  name        VARCHAR(200) NOT NULL,
  description TEXT,
  price       DECIMAL(10,2) NOT NULL,
  stock       INT,
  category    VARCHAR(50),
  sku         VARCHAR(50) UNIQUE
);

CREATE TABLE orders (
  id          INT PRIMARY KEY,
  user_id     INT NOT NULL,
  total       DECIMAL(10,2) NOT NULL,
  status      VARCHAR(20),
  created_at  TIMESTAMP NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE order_items (
  id          INT PRIMARY KEY,
  order_id    INT NOT NULL,
  product_id  INT NOT NULL,
  quantity    INT NOT NULL,
  unit_price  DECIMAL(10,2) NOT NULL,
  FOREIGN KEY (order_id)   REFERENCES orders(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);`;

// ─── Gutter line numbers ──────────────────────────────────────────────────────
function updateGutter() {
  const lines = ddlInput.value.split("\n").length;
  let html = "";
  for (let i = 1; i <= Math.max(lines, 10); i++) {
    html += `<div>${i}</div>`;
  }
  editorGutter.innerHTML = html;
  editorGutter.scrollTop = ddlInput.scrollTop;
}

ddlInput.addEventListener("input", updateGutter);
ddlInput.addEventListener("scroll", () => {
  editorGutter.scrollTop = ddlInput.scrollTop;
});

// Tab key support in editor
ddlInput.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const start = ddlInput.selectionStart;
    const end   = ddlInput.selectionEnd;
    ddlInput.value = ddlInput.value.slice(0, start) + "  " + ddlInput.value.slice(end);
    ddlInput.selectionStart = ddlInput.selectionEnd = start + 2;
    updateGutter();
  }
});

updateGutter();

// ─── Row stepper ─────────────────────────────────────────────────────────────
rowMinus.addEventListener("click", () => {
  const v = parseInt(rowCount.value, 10);
  if (v > 1) rowCount.value = v - 1;
});

rowPlus.addEventListener("click", () => {
  const v = parseInt(rowCount.value, 10);
  if (v < 500) rowCount.value = v + 1;
});

// ─── Clear / Load example ─────────────────────────────────────────────────────
clearEditorBtn.addEventListener("click", () => {
  ddlInput.value = "";
  updateGutter();
  ddlInput.focus();
});

loadExampleBtn.addEventListener("click", () => {
  ddlInput.value = EXAMPLE_DDL;
  updateGutter();
  ddlInput.focus();
  showToast("Example DDL loaded", "success");
});

// ─── Pipeline animation helpers ───────────────────────────────────────────────
function resetPipeline() {
  pSteps.forEach(s => { s.className = "pipeline-step"; });
  document.querySelectorAll(".pipeline-connector").forEach(c => c.classList.remove("lit"));
}

function activateStep(index) {
  resetPipeline();
  pSteps.forEach((s, i) => {
    if (i < index) s.classList.add("done");
    else if (i === index) s.classList.add("active");
  });
  document.querySelectorAll(".pipeline-connector").forEach((c, i) => {
    if (i < index) c.classList.add("lit");
  });
  if (pipelineMessages[index]) {
    loadingLabel.textContent = pipelineMessages[index];
  }
}

function completeAllSteps() {
  pSteps.forEach(s => { s.className = "pipeline-step done"; });
  document.querySelectorAll(".pipeline-connector").forEach(c => c.classList.add("lit"));
}

// ─── Panel state helpers ──────────────────────────────────────────────────────
function showState(state) {
  emptyState.style.display   = "none";
  loadingState.style.display = "none";
  errorState.style.display   = "none";
  results.style.display      = "none";

  if (state === "empty")   emptyState.style.display   = "flex";
  if (state === "loading") loadingState.style.display = "flex";
  if (state === "error")   errorState.style.display   = "flex";
  if (state === "results") results.style.display      = "flex";
}

// ─── Toast ────────────────────────────────────────────────────────────────────
let toastTimer = null;

function showToast(msg, type = "") {
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = "toast"; }, 2800);
}

// ─── Generate ─────────────────────────────────────────────────────────────────
generateBtn.addEventListener("click", handleGenerate);

async function handleGenerate() {
  const ddl  = ddlInput.value.trim();
  const rows = parseInt(rowCount.value, 10);

  if (!ddl) {
    showToast("Please enter your SQL DDL first", "error");
    ddlInput.focus();
    return;
  }

  if (isNaN(rows) || rows < 1 || rows > 500) {
    showToast("Row count must be between 1 and 500", "error");
    return;
  }

  generateBtn.disabled = true;
  showState("loading");
  resetPipeline();

  // Simulate step-through animation during the API call
  let stepIndex = 0;
  activateStep(stepIndex);

  const stepInterval = setInterval(() => {
    stepIndex = Math.min(stepIndex + 1, pSteps.length - 1);
    activateStep(stepIndex);
  }, 1800);

  try {
    const response = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ddl, rows })
    });

    clearInterval(stepInterval);
    completeAllSteps();
    await new Promise(r => setTimeout(r, 400));  // Let "done" state show

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    lastResult = data;
    renderResults(data);
    updateMetaRow(data);
    loadCacheStats();

  } catch (err) {
    clearInterval(stepInterval);
    errorMessage.textContent = err.message || "Network error. Is the backend running?";
    showState("error");
  } finally {
    generateBtn.disabled = false;
  }
}

dismissError.addEventListener("click", () => showState("empty"));

// ─── Render results ───────────────────────────────────────────────────────────
function renderResults(data) {
  showState("results");
  tabBar.innerHTML = "";
  tabContent.innerHTML = "";
  resultsBadge.textContent = `${data.tables.length} table${data.tables.length !== 1 ? "s" : ""}`;

  // Table tabs
  data.tables.forEach((table, idx) => {
    // Tab button
    const btn = document.createElement("button");
    btn.className = `tab-btn${idx === 0 ? " active" : ""}`;
    btn.setAttribute("role", "tab");
    btn.dataset.tab = table.name;
    btn.innerHTML = `
      <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" style="opacity:0.6">
        <path d="M2 3h12v2H2V3zm0 4h12v2H2V7zm0 4h8v2H2v-2z"/>
      </svg>
      ${escHtml(table.name)}
      <span class="tab-count">${table.total_rows}</span>
    `;
    btn.addEventListener("click", () => switchTab(table.name));
    tabBar.appendChild(btn);

    // Pane
    const pane = document.createElement("div");
    pane.className = `tab-pane${idx === 0 ? " active" : ""}`;
    pane.id = `pane-${table.name}`;
    pane.innerHTML = buildTablePane(table, data);
    tabContent.appendChild(pane);

    // Wire subtabs
    wireSubtabs(pane, table);
  });

  // Seed-all tab
  const seedBtn = document.createElement("button");
  seedBtn.className = "tab-btn";
  seedBtn.dataset.tab = "__seed_all__";
  seedBtn.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" style="opacity:0.6">
      <path d="M1 2h14v2H1V2zm0 5h14v2H1V7zm0 5h14v2H1v-2z"/>
    </svg>
    seed_all.sql
  `;
  seedBtn.addEventListener("click", () => switchTab("__seed_all__"));
  tabBar.appendChild(seedBtn);

  const seedPane = document.createElement("div");
  seedPane.className = "tab-pane";
  seedPane.id = "pane-__seed_all__";
  seedPane.innerHTML = `
    <div class="code-view" style="position:relative;flex:1;">
      <button class="copy-code-btn" data-copy="seed_all">Copy</button>
      <pre class="code-block active" id="seedAllCode">${escHtml(data.seed_all)}</pre>
    </div>
  `;
  seedPane.querySelector(".copy-code-btn").addEventListener("click", () => {
    copyText(data.seed_all, "seed_all.sql copied!");
  });
  tabContent.appendChild(seedPane);

  activeTable = data.tables[0]?.name || null;
}

function buildTablePane(table, fullData) {
  const colsHtml = table.columns.map(c => `<th>${escHtml(c)}</th>`).join("");
  const rowsHtml = table.data.map(row => {
    const cells = table.columns.map(c => `<td title="${escHtml(String(row[c] ?? ''))}">${escHtml(String(row[c] ?? ''))}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  const previewHtml = `
    <div class="preview-wrap active" id="preview-${table.name}">
      <table class="preview-table">
        <thead><tr>${colsHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
      ${table.total_rows > 5 ? `<p style="margin-top:10px;font-size:11px;color:var(--text-300);font-family:var(--font-mono);">Showing 5 of ${table.total_rows} rows</p>` : ""}
    </div>`;

  const sqlHtml = `
    <div class="code-view" style="display:none;position:relative;flex:1;" id="sqlview-${table.name}">
      <button class="copy-code-btn" data-copy="sql">Copy SQL</button>
      <pre class="code-block active">${escHtml(table.sql)}</pre>
    </div>`;

  const csvHtml = `
    <div class="code-view" style="display:none;position:relative;flex:1;" id="csvview-${table.name}">
      <button class="copy-code-btn" data-copy="csv">Copy CSV</button>
      <pre class="code-block active">${escHtml(table.csv)}</pre>
    </div>`;

  // Build mapper info from the full data
  const mapperRows = table.columns.map(col => {
    const isPK = table.data.length > 0;  // placeholder; actual mapping info not in response
    return `<tr>
      <td>${escHtml(col)}</td>
      <td>${escHtml(String(table.data[0]?.[col] ?? '—'))}</td>
    </tr>`;
  }).join("");

  return `
    <div class="subtab-bar">
      <button class="subtab-btn active" data-subtab="preview">Preview</button>
      <button class="subtab-btn" data-subtab="sql">SQL</button>
      <button class="subtab-btn" data-subtab="csv">CSV</button>
    </div>
    <div class="subtab-content" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      ${previewHtml}
      ${sqlHtml}
      ${csvHtml}
    </div>`;
}

function wireSubtabs(pane, table) {
  const subtabBtns = pane.querySelectorAll(".subtab-btn");
  const previewWrap = pane.querySelector(`#preview-${table.name}`);
  const sqlView     = pane.querySelector(`#sqlview-${table.name}`);
  const csvView     = pane.querySelector(`#csvview-${table.name}`);

  const views = {
    preview: previewWrap,
    sql: sqlView,
    csv: csvView,
  };

  subtabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      subtabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const key = btn.dataset.subtab;
      Object.entries(views).forEach(([k, el]) => {
        if (!el) return;
        el.style.display = (k === key) ? (key === "preview" ? "block" : "block") : "none";
      });
    });
  });

  // Wire copy buttons in sql/csv views
  sqlView?.querySelector(".copy-code-btn")?.addEventListener("click", () => {
    const text = sqlView.querySelector("pre").textContent;
    copyText(text, `${table.name}.sql copied!`);
  });
  csvView?.querySelector(".copy-code-btn")?.addEventListener("click", () => {
    const text = csvView.querySelector("pre").textContent;
    copyText(text, `${table.name}.csv copied!`);
  });
}

function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  document.querySelectorAll(".tab-pane").forEach(p => {
    p.classList.toggle("active", p.id === `pane-${name}`);
  });
  activeTable = name;
}

// ─── Meta row ─────────────────────────────────────────────────────────────────
function updateMetaRow(data) {
  metaRow.style.display = "flex";
  tokensUsed.textContent = data.tokens_used > 0 ? data.tokens_used.toLocaleString() : "0 (cached)";
  tableCount.textContent = data.table_count;
  cacheHit.textContent   = data.tokens_used === 0 ? "✓ Cache" : "Groq API";
}

// ─── Copy seed all ────────────────────────────────────────────────────────────
copySeedBtn.addEventListener("click", () => {
  if (lastResult?.seed_all) copyText(lastResult.seed_all, "seed_all.sql copied!");
});

// ─── Download ZIP ─────────────────────────────────────────────────────────────
downloadBtn.addEventListener("click", async () => {
  if (!lastResult) return;

  downloadBtn.disabled = true;
  downloadBtn.textContent = "Preparing…";

  try {
    const resp = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tables: lastResult.tables,
        seed_all: lastResult.seed_all
      })
    });

    if (!resp.ok) throw new Error("Download failed");

    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = "test_data.zip";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Download started!", "success");

  } catch (err) {
    showToast(`Download failed: ${err.message}`, "error");
  } finally {
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = `
      <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 10.5L4.5 7H7V2h2v5h2.5L8 10.5zM2 13h12v1.5H2V13z"/>
      </svg>
      Download ZIP`;
  }
});

// ─── Cache management ─────────────────────────────────────────────────────────
async function loadCacheStats() {
  try {
    const resp = await fetch(`${API_BASE}/api/cache/stats`);
    const data = await resp.json();
    const kb   = (data.size_bytes / 1024).toFixed(1);
    cacheLabel.textContent = data.entries > 0
      ? `Cache: ${data.entries} entries · ${kb}KB`
      : "Cache: empty";
  } catch {
    cacheLabel.textContent = "Cache: unavailable";
  }
}

clearCacheBtn.addEventListener("click", async () => {
  if (!confirm("Clear the mapper cache? This will force new Groq API calls next time.")) return;

  try {
    const resp = await fetch(`${API_BASE}/api/cache/clear`, { method: "DELETE" });
    const data = await resp.json();
    if (resp.ok) {
      showToast("Cache cleared ✓", "success");
      cacheLabel.textContent = "Cache: empty";
    } else {
      showToast(data.error || "Clear failed", "error");
    }
  } catch {
    showToast("Could not reach backend", "error");
  }
});

// ─── Modal ────────────────────────────────────────────────────────────────────
mapModalClose.addEventListener("click", () => { mapModal.style.display = "none"; });
mapModal.addEventListener("click", (e) => {
  if (e.target === mapModal) mapModal.style.display = "none";
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") mapModal.style.display = "none";
});

// ─── Utilities ────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function copyText(text, successMsg = "Copied!") {
  try {
    await navigator.clipboard.writeText(text);
    showToast(successMsg, "success");
  } catch {
    // Fallback for non-HTTPS
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    showToast(successMsg, "success");
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
showState("empty");
loadCacheStats();

// Auto-refresh cache stats every 30s
setInterval(loadCacheStats, 30000);
