const $ = (id) => document.getElementById(id);
const state = {suite: "classification", split: "dev", config: null, revision: null, dirty: false, editorDirty: false, busy: false, report: null, catalog: {}, index: 0};
const settingLabels = {
  normalize_labels: ["Normalize labels", "Ignore letter case and outer whitespace. Extra explanations still fail."],
  allow_extra_fields: ["Allow extra fields", "Required fields and their values are always checked."],
  check_outcome: ["Verify simulated outcome", "Check the lookup result or simulated ticket creation as well as the call."],
  require_retrieval: ["Require complete retrieval", "Every reference document must be retrieved. Answer and citation checks remain active."],
  require_final_state: ["Verify reported final state", "The final claim must match replayed tool state. Goal and trace checks remain active."],
};
const percent = (n) => `${(n * 100).toFixed(1).replace(/\.0$/, "")}%`;
const pretty = (x) => typeof x === "string" ? x : JSON.stringify(x, null, 2);
function status(text, error = false) { $("status").textContent = text; $("status").classList.toggle("error", error); }
async function api(path, data) {
  const response = await fetch(`./api/${path}`, data === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}
function controls() {
  document.querySelectorAll("[data-lock]").forEach(el => { el.disabled = state.busy; });
  $("editor-fields").disabled = state.busy || state.split === "holdout";
  $("editor-fields").hidden = state.split === "holdout";
  $("threshold").disabled = state.busy || state.split === "holdout";
  $("download-report").disabled = !state.report || state.busy;
  $("download-html").disabled = !state.report || state.busy;
  $("holdout-note").hidden = state.split !== "holdout";
}
async function task(action) {
  if (state.busy) return;
  state.busy = true; controls();
  try { await action(); } catch (e) { status(e.message, true); }
  finally { state.busy = false; controls(); }
}
function markDirty() {
  state.dirty = true;
  $("save-state").textContent = "Unsaved draft";
  if (state.report) {
    state.report = null; $("results-area").hidden = true; $("download-report").disabled = true;
    status("The eval changed. Rerun to get results for this draft.");
  }
}
function drawEditor() {
  const list = $("case-picker"); list.replaceChildren();
  state.config.cases.forEach((c, i) => { const option = document.createElement("option"); option.value = i; option.textContent = c.id; list.append(option); });
  state.index = Math.min(state.index, state.config.cases.length - 1);
  list.value = state.index;
  const c = state.config.cases[state.index];
  $("case-input").value = pretty(c.input); $("case-expected").value = pretty(c.expected); $("case-tags").value = c.tags.join(", ");
  $("input-label").textContent = typeof c.input === "string" ? "Input" : "Input · JSON object";
  $("expected-label").textContent = state.suite === "classification" ? "Expected label · Hardware, Software, or Other" : "Expected answer · JSON object";
  state.editorDirty = false;
}
function applyEditor() {
  if (!state.editorDirty || state.split === "holdout") return;
  const text = $("case-expected").value.trim();
  let expected = text;
  if (state.suite !== "classification") {
    try { expected = JSON.parse(text); } catch { throw new Error("Expected answer must be valid JSON. Fix it before running or saving."); }
  } else if (!["Hardware", "Software", "Other"].includes(text)) {
    throw new Error("Expected label must be Hardware, Software, or Other.");
  }
  if (!$("case-input").value.trim()) throw new Error("A case needs a nonempty input.");
  const current = state.config.cases[state.index];
  let input = $("case-input").value;
  if (typeof current.input !== "string") {
    try { input = JSON.parse(input); } catch { throw new Error("Input must be valid JSON."); }
  }
  Object.assign(current, {input, expected, tags: [...new Set($("case-tags").value.split(",").map(t => t.trim()).filter(Boolean))]});
  state.editorDirty = false; markDirty();
}
function drawConfig() {
  const meta = state.catalog[state.suite];
  $("suite-description").textContent = meta.description;
  $("grader-name").textContent = meta.grader;
  $("lesson").textContent = meta.lesson;
  $("settings").replaceChildren();
  for (const [key, value] of Object.entries(state.config.settings)) {
    const label = document.createElement("label"); label.className = "check-control";
    const input = document.createElement("input"); input.type = "checkbox"; input.checked = value; input.dataset.lock = "";
    input.addEventListener("change", () => { state.config.settings[key] = input.checked; markDirty(); });
    const copy = document.createElement("span"); const strong = document.createElement("strong"); strong.textContent = settingLabels[key][0]; const detail = document.createElement("small"); detail.textContent = settingLabels[key][1]; copy.append(strong, detail); label.append(input, copy); $("settings").append(label);
  }
  drawEditor(); drawSplit();
}
function drawSplit() {
  const holdout = state.split === "holdout";
  $("threshold").value = holdout ? .8 : state.config.threshold;
  $("threshold-value").value = percent(Number($("threshold").value));
  $("dataset-note").textContent = holdout ? `${state.catalog[state.suite].holdout_count} reserved examples · original settings · use after development tuning` : `${state.config.cases.length} development cases · edits are included in your next run`;
  controls();
}
async function loadSuite() {
  const data = await api(`config?suite=${state.suite}`);
  state.config = data.config; state.revision = data.revision; state.dirty = false; state.report = null; state.index = 0;
  $("save-state").textContent = data.saved ? "Saved local profile" : "Bundled defaults";
  $("results-area").hidden = true; drawConfig();
  const candidates = (await api(`candidates?suite=${state.suite}`)).candidates;
  for (const id of ["candidate", "before-candidate"]) {
    $(id).replaceChildren();
    for (const c of candidates) {
      const option = document.createElement("option"); option.value = c.name; option.textContent = `${c.name} · ${c.kind}`; $(id).append(option);
    }
  }
  $("candidate").value = "improved"; $("before-candidate").value = "baseline";
  status("Ready. Compare both candidates on the same dataset, or tune the eval below.");
}
function badge(text, kind) { const el = document.createElement("span"); el.className = `result-badge ${kind}`; el.textContent = text; return el; }
function cell(text, className = "") { const el = document.createElement("td"); el.textContent = text; el.className = className; return el; }
function renderRows() {
  const comparison = state.report?.after;
  const report = comparison || state.report;
  if (!report) return;
  const entries = comparison ? state.report.changes : report.results.map(after => ({after, change: "unchanged"}));
  const visible = entries.filter(c => $("filter").value === "all" || $("filter").value === "failed" && !c.after.passed || $("filter").value === "changed" && c.change !== "unchanged" || $("filter").value === "regressed" && c.change === "regressed");
  $("results-body").replaceChildren();
  for (const item of visible) {
    const result = item.after, row = document.createElement("tr");
    if (!result.passed) row.className = "failed-row";
    const inputCell = cell("", "ticket-cell"); const id = document.createElement("strong"); id.textContent = result.id;
    const text = document.createElement(typeof result.input === "string" ? "p" : "details");
    if (typeof result.input === "string") text.textContent = result.input;
    else { const title = document.createElement("summary"); title.textContent = "Inspect input"; const content = document.createElement("pre"); content.textContent = pretty(result.input); text.append(title, content); }
    const tags = document.createElement("div"); tags.className = "tag-list";
    result.tags.forEach(t => { const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = t; tags.append(tag); });
    inputCell.append(id, text, tags);
    const outputCell = cell("", "output-cell");
    if (comparison) { const before = document.createElement("pre"); before.textContent = pretty(item.before.actual); outputCell.append(badge(item.before.passed ? "PASS" : "FAIL", item.before.passed ? "pass" : "fail"), before); }
    else { const output = document.createElement("pre"); output.textContent = pretty(result.actual); outputCell.append(output); }
    const verdict = cell("", "output-cell"); verdict.append(badge(result.passed ? "PASS" : "FAIL", result.passed ? "pass" : "fail"));
    if (comparison) { if (item.change !== "unchanged") verdict.append(badge(item.change, item.change === "improved" ? "pass" : "fail")); const actual = document.createElement("pre"); actual.textContent = pretty(result.actual); verdict.append(actual); }
    const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Grader checks"; details.append(summary);
    for (const check of result.checks) { const p = document.createElement("p"); p.textContent = `${check.passed ? "✓" : "×"} ${check.name}: ${check.detail}`; details.append(p); }
    verdict.append(details); row.append(inputCell, cell(pretty(result.expected), "expected-cell"), outputCell, verdict); $("results-body").append(row);
  }
  $("empty-results").hidden = visible.length > 0;
}
function renderReport(payload) {
  state.report = payload;
  const comparison = Boolean(payload.after), report = payload.after || payload;
  $("score-label").textContent = `${report.candidate.name} · ${report.suite === "response_quality" ? "human agreement" : "pass rate"}`;
  $("score").textContent = percent(report.score); $("score-detail").textContent = `${report.passed}/${report.total} cases pass every check`;
  $("change").textContent = comparison ? `${payload.delta >= 0 ? "+" : ""}${(payload.delta * 100).toFixed(0)} pp` : `${report.failed}`;
  $("change-label").textContent = comparison ? "Change from baseline" : "Failed cases";
  $("change-detail").textContent = comparison ? `${payload.improved} improved · ${payload.regressed} regressed · baseline ${percent(payload.before.score)}` : "Inspect the failed grader checks below";
  const passedGate = payload.passed_gate ?? report.passed_gate;
  $("gate").textContent = passedGate ? "PASS" : "FAIL"; $("gate").className = passedGate ? "good" : "error";
  $("gate-detail").textContent = (payload.gates || report.gates).map(g => `${g.name}: ${g.passed ? "pass" : "fail"}`).join(" · ");
  $("report-context").textContent = `${report.suite} · ${report.split} · ${report.candidate.kind} · ${new Date(report.created_at).toLocaleString()} · ${report.trials} trial(s)`;
  $("before-heading").textContent = comparison ? `${payload.before.candidate.name} output` : "Candidate output";
  $("report-origin").hidden = !payload.imported;
  $("report-origin").textContent = "Imported report: contents and measurements are user-supplied and not authenticated.";
  $("slice-grid").replaceChildren();
  for (const [tag, scores] of Object.entries(report.slices)) {
    const item = document.createElement("div"); item.className = "slice-item"; const label = document.createElement("div"); label.textContent = `${tag} · ${scores.passed}/${scores.total} · ${percent(scores.accuracy)}`; const meter = document.createElement("meter"); meter.min = 0; meter.max = scores.total; meter.value = scores.passed; meter.setAttribute("aria-label", `${tag} pass rate`); item.append(label, meter); $("slice-grid").append(item);
  }
  const measurements = $("measurements"); measurements.replaceChildren();
  const addMeasurement = (label, value) => { const p = document.createElement("p"); p.textContent = `${label}: ${value}`; measurements.append(p); };
  for (const [name, values] of Object.entries(report.metrics.checks)) addMeasurement(name, `${values.passed}/${values.total} · ${percent(values.rate)}`);
  for (const [name, values] of Object.entries(report.metrics.measurements)) addMeasurement(name, `${values.mean.toFixed(3)} mean · ${values.count} measured outputs`);
  addMeasurement("Candidate latency", `median ${report.metrics.candidate_latency_ms.median} ms · p95 ${report.metrics.candidate_latency_ms.p95} ms`);
  addMeasurement("Token usage", `${pretty(report.metrics.usage)} · supplied for ${report.metrics.usage_coverage}/${report.total} executions`);
  addMeasurement("Trial scores", report.metrics.trial_scores.map(percent).join(", "));
  addMeasurement("Cases with variable pass/fail", `${report.metrics.unstable_cases}/${report.case_count}`);
  addMeasurement("Execution errors", report.execution_errors);
  if (report.metrics.confusion_matrix) {
    addMeasurement("Macro-F1 (normalized labels)", report.metrics.macro_f1.toFixed(3));
    const table = document.createElement("table"); const caption = document.createElement("caption"); caption.textContent = "Confusion matrix · expected rows, predicted columns"; table.append(caption);
    const labels = ["Hardware", "Software", "Other", "invalid"];
    const header = document.createElement("tr");
    for (const value of ["Expected", ...labels]) { const th = document.createElement("th"); th.textContent = value; header.append(th); }
    table.append(header);
    for (const [label, values] of Object.entries(report.metrics.confusion_matrix)) {
      const tr = document.createElement("tr"); tr.append(cell(label)); labels.forEach(k => tr.append(cell(values[k]))); table.append(tr);
    }
    const wrap = document.createElement("div"); wrap.className = "table-wrap"; wrap.append(table); measurements.append(wrap);
  }
  renderRows(); $("results-area").hidden = false;
  status(comparison ? `Comparison finished on ${report.total} identical cases. Both candidates used the same grader and threshold.` : `Finished: ${report.passed}/${report.total} cases passed.`);
}
function download(name, data, type = "application/json") {
  const url = URL.createObjectURL(new Blob([type === "application/json" ? JSON.stringify(data, null, 2) + "\n" : data], {type}));
  const link = document.createElement("a"); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function runOptions() {
  const slices = {};
  for (const entry of $("min-slices").value.split(",").map(x => x.trim()).filter(Boolean)) {
    const match = entry.match(/^(.+)=(0(?:\.\d+)?|1(?:\.0+)?)$/);
    if (!match) throw new Error("Use slice minimums like retry=1, multilingual=0.8");
    slices[match[1].trim()] = Number(match[2]);
  }
  return {trials: Number($("trials").value), gates: {critical_tags: $("critical-tags").value.split(",").map(x => x.trim()).filter(Boolean), min_slices: slices, fail_on_regression: $("fail-regression").checked}};
}
async function refreshHistory() {
  const runs = (await api("runs")).runs;
  for (const id of ["history-before", "history-after"]) {
    const previous = $(id).value; $(id).replaceChildren();
    for (const run of runs) {
      const option = document.createElement("option"); option.value = run.id; option.textContent = `${run.suite} · ${run.split} · ${run.candidate} · ${percent(run.score)}${run.imported ? " · imported" : ""} · ${new Date(run.created_at).toLocaleString()}`; $(id).append(option);
    }
    if (runs.some(r => r.id === previous)) $(id).value = previous;
  }
  if (state.report?.run_id) $("history-after").value = state.report.run_id;
}
async function showSaved(payload) { renderReport(payload); await refreshHistory(); }
$("compare").addEventListener("click", () => task(async () => { applyEditor(); status("Comparing both candidates…"); await showSaved(await api("compare", {suite: state.suite, split: state.split, config: state.config, before: $("before-candidate").value, after: $("candidate").value, ...runOptions()})); }));
$("run").addEventListener("click", () => task(async () => { applyEditor(); status("Running the selected candidate…"); await showSaved(await api("run", {suite: state.suite, split: state.split, candidate: $("candidate").value, config: state.config, ...runOptions()})); }));
$("suite").addEventListener("change", () => task(async () => {
  if ((state.dirty || state.editorDirty) && !confirm("Discard this unsaved draft and switch suites? Export or save it first to keep it.")) { $("suite").value = state.suite; return; }
  const previous = state.suite;
  state.suite = $("suite").value;
  try { await loadSuite(); } catch (e) { state.suite = previous; $("suite").value = previous; throw e; }
}));
$("split").addEventListener("change", () => task(async () => {
  try { applyEditor(); } catch (e) { $("split").value = state.split; throw e; }
  state.split = $("split").value; state.report = null; $("results-area").hidden = true; drawSplit();
  status(state.split === "holdout" ? "Holdout uses the bundled cases and original settings. Your development draft is preserved." : "Development draft restored.");
}));
$("threshold").addEventListener("input", () => { state.config.threshold = Number($("threshold").value); $("threshold-value").value = percent(state.config.threshold); markDirty(); });
["case-input", "case-expected", "case-tags"].forEach(id => $(id).addEventListener("input", () => { state.editorDirty = true; markDirty(); }));
$("case-picker").addEventListener("change", () => task(async () => { const next = Number($("case-picker").value); try { applyEditor(); } catch (e) { $("case-picker").value = state.index; throw e; } state.index = next; drawEditor(); }));
$("apply-case").addEventListener("click", () => task(async () => { applyEditor(); status("Case applied to the draft. Run the eval or save the profile."); }));
$("add-case").addEventListener("click", () => task(async () => {
  applyEditor(); if (state.config.cases.length >= 500) throw new Error("A profile can contain at most 500 cases.");
  const copy = structuredClone(state.config.cases[state.index]); let n = 1; while (state.config.cases.some(c => c.id === `custom-${n}`)) n++;
  copy.id = `custom-${n}`; copy.tags = ["custom"]; state.config.cases.push(copy); state.index = state.config.cases.length - 1; markDirty(); drawEditor(); drawSplit(); status("Added a copy of the selected case. Edit its input and expected answer.");
}));
$("delete-case").addEventListener("click", () => task(async () => { if (state.config.cases.length === 1) throw new Error("Keep at least one case."); state.config.cases.splice(state.index, 1); markDirty(); drawEditor(); drawSplit(); status("Case removed from the draft."); }));
$("save").addEventListener("click", () => task(async () => {
  applyEditor(); const saved = await api("save", {suite: state.suite, config: state.config, revision: state.revision}); state.revision = saved.revision; state.dirty = false; $("save-state").textContent = "Saved local profile"; status("Tuning saved on this computer. The previous version is in local/history.");
}));
$("reset").addEventListener("click", () => task(async () => { if (!confirm("Restore the bundled defaults? Saved versions remain in local/history; unsaved edits will be discarded.")) return; await api("reset", {suite: state.suite, revision: state.revision}); await loadSuite(); status("Bundled defaults restored."); }));
$("export").addEventListener("click", () => task(async () => { applyEditor(); download(`${state.suite}-profile.json`, state.config); status("Profile exported. It contains the dataset, grading settings, and threshold."); }));
$("import").addEventListener("change", () => task(async () => {
  const file = $("import").files[0]; if (!file) return;
  if (file.size > 1000000) throw new Error("Profile is too large.");
  const config = JSON.parse(await file.text());
  // The shared Python validator checks the entire profile before accepting it.
  state.config = await api("validate-profile", {suite: state.suite, config});
  state.index = 0; markDirty(); drawConfig(); $("import").value = ""; status("Profile imported into the draft. Save tuning to keep it.");
}));
$("filter").addEventListener("change", renderRows);
$("download-report").addEventListener("click", () => { const r = state.report.after || state.report; download(`${r.suite}-${r.split}-report.json`, state.report); });
$("download-html").addEventListener("click", () => task(async () => {
  const r = state.report.after || state.report;
  const result = await api("export-html", {report: state.report}); download(`${r.suite}-${r.split}.html`, result.html, "text/html");
}));
$("open-run").addEventListener("click", () => task(async () => {
  if (!$("history-after").value) throw new Error("Run an eval or import a report first.");
  renderReport(await api(`report?id=${$("history-after").value}`)); $("results-area").scrollIntoView({behavior: "smooth"});
}));
$("compare-runs").addEventListener("click", () => task(async () => {
  await showSaved(await api("compare-runs", {before: $("history-before").value, after: $("history-after").value})); $("results-area").scrollIntoView({behavior: "smooth"});
}));
$("import-report").addEventListener("change", () => task(async () => {
  const file = $("import-report").files[0]; if (!file) return;
  if (file.size > 20000000) throw new Error("Report exceeds 20 MB.");
  await showSaved(await api("import-report", {report: JSON.parse(await file.text())}));
  $("import-report").value = ""; status("Report imported and saved locally.");
}));
window.addEventListener("beforeunload", (event) => { if (state.dirty || state.editorDirty) { event.preventDefault(); event.returnValue = ""; } });
task(async () => {
  const catalog = await api("suites"); state.catalog = Object.fromEntries(catalog.suites.map(s => [s.id, s]));
  for (const s of catalog.suites) { const option = document.createElement("option"); option.value = s.id; option.textContent = s.title; $("suite").append(option); }
  const requestedSuite = new URLSearchParams(location.search).get("suite");
  if (Object.hasOwn(state.catalog, requestedSuite)) { state.suite = requestedSuite; $("suite").value = requestedSuite; }
  await loadSuite(); await refreshHistory();
});
