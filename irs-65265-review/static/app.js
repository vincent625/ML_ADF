"use strict";
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value === undefined ? "" : value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pretty = value => esc(typeof value === "string" ? value : JSON.stringify(value, null, 2));
const badge = (text, kind) => `<span class="badge ${esc(kind || text)}">${esc(text)}</span>`;
let state, evidence, tab = "sources", scenario = "wrong-primer", requirement = "R05", selectedTest, proposal;
let testFilter = "attention", busy = false;

async function api(path, body) {
  const response = await fetch(path, body ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function notice(message, error = false) {
  $("#notice").textContent = message;
  $("#notice").className = error ? "error" : "";
}
async function action(work) {
  if (busy) return;
  busy = true;
  const enabledButtons = [...document.querySelectorAll("button")].filter(b => !b.disabled);
  enabledButtons.forEach(b => b.disabled = true);
  try { await work(); } catch (error) { notice(error.message, true); }
  finally { busy = false; enabledButtons.filter(b => b.isConnected).forEach(b => b.disabled = false); }
}
async function refresh() {
  state = await api(`/api/state?scenario=${encodeURIComponent(scenario)}`);
  const current = state.latest.results.find(r => r.id === selectedTest);
  if (!current || current.status === "pass") {
    selectedTest = (state.latest.results.find(r => r.status !== "pass") || state.latest.results[0]).id;
  }
  $("#scenario").innerHTML = state.scenarios.map(s => `<option value="${esc(s.id)}" ${s.id === scenario ? "selected" : ""}>${esc(s.name)}</option>`).join("");
  render();
}
function sourceExcerpt(id) {
  const excerpt = evidence.excerpts[id];
  const source = excerpt.source;
  return `<p class="muted">${esc(excerpt.kind)} &middot; ${source.startsWith("https://") ? `<a target="_blank" rel="noreferrer" href="${esc(source)}">Open source</a>` : esc(source)}</p><pre>${pretty(excerpt.text)}</pre>`;
}
function render() {
  const counts = state.summary;
  $("#metrics").innerHTML = [
    [evidence.requirements.length, "requirement families / review candidates"],
    [`${state.source_checks.observed}/${state.source_checks.total}`, "captured-source facts observed"],
    [counts.pass || 0, "current synthetic assertions pass"],
    [(counts.fail || 0) + (counts.stale || 0), `${counts.fail || 0} fail / ${counts.stale || 0} stale`],
    ["BLOCKED", "real ADF assembly / installation"],
  ].map(([value,label]) => `<div class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join("");
  document.querySelectorAll("nav button").forEach(b => {b.classList.toggle("active",b.dataset.tab === tab);b.setAttribute("aria-current",b.dataset.tab === tab ? "page" : "false");});
  const views = {sources: sourcesView, requirements: requirementsView, components: componentsView,
    runner: runnerView, impact: impactView, export: exportView};
  $("#content").innerHTML = views[tab]();
}
function sourcesView() {
  const c = evidence.coverage;
  return `<div class="grid">
    <article class="card"><p class="eyebrow">THE REAL PLANNED BASELINE</p><h3>Two weeks bundle. One week sanity.</h3>
      ${evidence.schedule.map(p => `<div class="phase"><strong>${esc(p.phase)}</strong><span>${esc(p.start || "")}${p.end ? " to " + esc(p.end) : ""} ${esc(p.label)}</span></div>`).join("")}
      <p class="muted">Planned elapsed time from the previously reviewed schedule screenshot, not measured labor. Later Mol Bio work is separate. The original screenshot is not in this package.</p>
      <div class="warning">No production AI-savings claim. Local timings measure only this prototype.</div></article>
    <article class="card"><p class="eyebrow">SOURCE COMPLETENESS</p><h3>Make the gaps visible</h3>
      <strong>${c.snapshot_comments_loaded} / ${c.snapshot_comment_total} comments loaded</strong><progress value="${c.snapshot_comments_loaded}" max="${c.snapshot_comment_total}" aria-label="Loaded comments"></progress>
      <p>Attachments: UI badge <strong>${c.ui_attachment_badge}</strong> vs cached <strong>${c.api_attachment_count}</strong>. Captured metadata: <strong>${c.attachment_metadata_loaded}</strong>.</p>
      <p>${esc(evidence.xray)}</p><p class="warning">${esc(evidence.real_assembly)}</p>
      <p class="muted">Original HTML / resource ZIP: ${esc(evidence.original_uploads)}. The supplied ZIP is the review package itself.</p></article>
    <article class="card wide"><h3>Three pinned implementation sources</h3><div class="scroll"><table><thead><tr><th>Scope</th><th>Pinned revision</th><th>Inventory</th><th>Captured patches</th></tr></thead><tbody>
      ${evidence.prs.map(p => `<tr><td><a href="${esc(p.pr_url)}" target="_blank" rel="noreferrer">${esc(p.scope)} PR</a></td><td><code>${esc(p.head_sha)}</code></td><td>${p.inventory_count} entries</td><td>${p.selected_patch_count} selected excerpts</td></tr>`).join("")}
      </tbody></table></div><p class="muted">Live metadata and selected pinned files rechecked on 2026-10-23. Inventory does not mean every file was inspected. No repository was modified.</p></article>
    <article class="card wide"><h3>Evidence inventory &amp; historical references</h3>
      <p>${evidence.links.length} unique business URLs: ${Object.entries(evidence.url_counts).map(([k,v]) => `${v} ${esc(k)}`).join(" / ")}.</p>
      <details><summary>Source limitations</summary><ul>${evidence.limitations.map(x => `<li>${esc(x)}</li>`).join("")}</ul><p>Original HTML SHA-256 (recorded, not rehashed here): <code>${esc(c.source_sha256)}</code></p></details>
      <details><summary>${evidence.history.length} recorded run references &mdash; not current passes</summary><div class="scroll"><table><thead><tr><th>Run</th><th>Source / dates</th><th>Evidence status</th></tr></thead><tbody>${evidence.history.map(h => `<tr><td><a href="${esc(h.url)}" target="_blank" rel="noreferrer">${esc(h.run_id)}</a></td><td>${esc(h.sources)}<br>${h.dates.map(d => `${esc(d.created)} / updated ${esc(d.updated)}`).join("<br>")}</td><td>${esc(h.evidence_status)}</td></tr>`).join("")}</tbody></table></div></details>
      <details><summary>All linked sources and retrieval status</summary><ul>${evidence.links.map(l => `<li><a href="${esc(l.url)}" target="_blank" rel="noreferrer">${esc(l.type)}: ${esc(l.url)}</a><br><small>${esc(l.review_status)}</small></li>`).join("")}</ul></details>
    </article></div>`;
}
function requirementsView() {
  const req = evidence.requirements.find(r => r.id === requirement);
  const replay = evidence.ai_replay.filter(e => JSON.stringify(e.proposed_target).includes(req.id));
  return `<p class="info">AI mode: ${esc(evidence.ai_mode)}. Interpretations remain candidates. Exact observations and deterministic assertions are separate.</p>
    <div class="split"><article class="card"><h3>${evidence.requirements.length} candidate families</h3><div class="requirement-list">${evidence.requirements.map(r => `<button class="requirement ${r.id === requirement ? "selected" : ""}" data-requirement="${r.id}"><strong>${r.id} &middot; ${esc(r.topic)}</strong>${badge(r.state,"history")}<small>${esc(r.scope)}</small></button>`).join("")}</div></article>
    <article class="card sticky"><h3>${req.id} / ${esc(req.topic)}</h3>${badge(req.state,"history")}<p>${esc(req.automation)}</p>
      <h4>Retrieved supporting evidence</h4>${sourceExcerpt(req.id)}
      <h4>Candidate interpretation / not source quotation</h4><pre>${pretty(req.expected)}</pre>
      ${replay.map(e => `<details open><summary>Stored AI replay ${esc(e.id)} / ${esc(e.task)}</summary><p>${esc(e.inputs.evidence)}</p><pre>${pretty(e.proposed_target)}</pre><small>${esc(e.label_review_status)} &middot; model trained: ${e.model_trained}</small></details>`).join("")}
      <p class="warning">R05 TVC is cancelled. R06 Tmap is inherited. R15/R16 are crossed-out history. R09 explicitly selects Motorhead for v0.0.3; later Manticore work is deferred.</p></article></div>
    <article class="card"><h3>Stored AI interpretation library / ${evidence.ai_replay.length} review candidates</h3><p class="muted">Credential-free replay of supplied interpretations, not newly generated model outputs. Retrieval uses this local release evidence; no live pretrained model is configured.</p>
      ${evidence.ai_replay.map(e => `<details><summary>${esc(e.id)} / ${esc(e.task)}</summary><p><strong>Supporting record:</strong> ${esc(e.inputs.source)}</p><blockquote>${esc(e.inputs.evidence)}</blockquote><pre>${pretty(e.proposed_target)}</pre><p class="muted">${esc(e.label_type)} / ${esc(e.label_review_status)} / release group ${esc(e.release_group)}</p></details>`).join("")}</article>
    <article class="card"><h3>Requirement-to-artifact coverage heatmap</h3><p class="muted">Cells derive from this fixture's latest run, not ticket closure. No mapped assertion means a gap or non-active history, never a pass.</p>
      <div class="scroll"><table><thead><tr><th>Candidate / state</th><th>DNA fixture</th><th>DNA+Fusion fixture</th><th>Observed artifact families</th></tr></thead><tbody>
      ${evidence.requirements.map(r => `<tr><td>${r.id} ${esc(r.topic)}<br><small>${esc(r.state)}</small></td>${["dna","fusion"].map(v => {
        const results = state.latest.results.filter(t => t.requirement === r.id && t.variant === v);
        const status = results.some(x => x.status === "stale") ? "stale" : results.some(x => x.status === "fail") ? "fail" : results.length ? "pass" : "gap";
        const notApplicable = r.id === "R02" && v === "dna";
        const historical = r.state === "cancelled" || r.state.startsWith("historical");
        return `<td>${badge(notApplicable ? "not applicable" : historical ? "history / no new test" : results.length ? `${results.length} ${status}` : "unmapped / review",notApplicable || historical ? "history" : status)}</td>`;
      }).join("")}<td>${esc([...new Set(state.latest.results.filter(t => t.requirement === r.id).map(t => t.component))].join(", ") || "No executable assertion / review required")}</td></tr>`).join("")}
      </tbody></table></div><p class="warning">R04 full actor refresh, inherited Tmap / OVAT, and VNS package mapping are unresolved. A partial source check is not full acceptance coverage.</p></article>`;
}
function componentsView() {
  return `<article class="card"><h3>Scoped requirement &rarr; component &rarr; variant &rarr; tests</h3>
    <div class="scroll"><svg class="graph" viewBox="0 0 1000 250" role="img" aria-label="R01 kit and R08 alignment affect both DNA and DNA Fusion; R18 RNA threshold affects Fusion only; CNV and MSI components are shared.">
      <path d="M180 45H260V90H380 M260 90V170H380 M180 125H300V90H380 M300 125V170H380 M570 90H650V50H730 M570 170H650V50 M570 170H680V190H730"/>
      <rect x="10" y="15" width="170" height="65" rx="8"/><text x="25" y="42">R01 / R08</text><text x="25" y="65">Kit / alignment</text>
      <rect x="10" y="100" width="170" height="65" rx="8"/><text x="25" y="128">R14 / R17</text><text x="25" y="151">Shared CNV / MSI</text>
      <rect x="380" y="55" width="190" height="65" rx="8"/><text x="405" y="83">DNA</text><text x="405" y="106">${state.latest.results.filter(r => r.variant === "dna").length} local cases</text>
      <rect x="380" y="145" width="190" height="65" rx="8"/><text x="405" y="174">DNA+Fusion</text><text x="405" y="197">${state.latest.results.filter(r => r.variant === "fusion").length} local cases</text>
      <rect x="730" y="15" width="250" height="65" rx="8"/><text x="750" y="43">Scoped test fingerprints</text><text x="750" y="65">Requirement / bytes / env</text>
      <rect x="730" y="155" width="250" height="65" rx="8"/><text x="750" y="183">R18 RNA threshold</text><text x="750" y="205">Fusion actor only</text>
    </svg></div><p class="muted">Diagram scrolls horizontally on narrow screens. The computed edges below list every mapped dependency.</p>
    <details><summary>Computed dependency edges (${state.test_count} cases)</summary><div class="scroll"><table><thead><tr><th>Requirement</th><th>Component</th><th>Variant / test</th><th>Mode</th></tr></thead><tbody>${state.latest.results.map(t => `<tr><td>${t.requirement}</td><td>${esc(t.component)}</td><td>${esc(t.id)}</td><td>${esc(t.execution_mode)}</td></tr>`).join("")}</tbody></table></div></details></article>
    <div class="grid"><article class="card"><h3>Compare final captured Git blobs</h3><p>Diff counts are not final-content identity. Removed inventory rows are retained as history, not active assets.</p>
      <div class="scroll"><table><thead><tr><th>Component</th><th>DNA / Fusion diff counts</th><th>Final metadata identity</th></tr></thead><tbody>${evidence.shared.filter(s => s.path.includes("copynumber_exon") || s.path.includes("MSI_IR") || s.path.endsWith("20260903_Manticore_cnv.h5") || s.path.endsWith("09_03_2026.msi.h5")).map(s => `<tr><td><code>${esc(s.path)}</code></td><td>${s.changes.dna} / ${s.changes.fusion}</td><td>${badge(s.sameGitBlob ? "same blob" : "different",s.sameGitBlob ? "pass" : "gap")}<br><code>${esc(s.dnaSha)}</code></td></tr>`).join("")}</tbody></table></div>
      <p class="muted">Metadata evidence only. Matching Git blob IDs do not validate baseline science or released ZIP contents.</p></article>
    <article class="card"><h3>Actual synthetic shared bytes</h3><p>Choose <strong>One shared script stale</strong> above to observe deliberately different fixture content.</p>
      ${state.shared_fixtures.map(s => `<h4>${esc(s.path)}</h4>${badge(s.same_bytes ? "matching fixture bytes" : "fixture drift",s.same_bytes ? "pass" : "fail")}<pre>DNA:    ${esc(s.hashes.dna)}\nFusion: ${esc(s.hashes.fusion)}</pre>`).join("")}
      <p class="info">The runner hashes actual files, independently of scenario names and the test-only mutation oracle.</p></article></div>`;
}
function runnerView() {
  const results = state.latest.results;
  const selected = results.find(r => r.id === selectedTest) || results[0];
  const rows = results.filter(r => testFilter === "all" || (testFilter === "attention" ? r.status !== "pass" : r.kind === "qc"));
  const hypothesis = selected.status === "pass" ? (selected.kind === "qc" ? "This conditional assertion matches the explicit simulated QC context. Pipeline completion and scientific/sample QC remain separate outcomes." : "The observed assertion matches the sandbox contract. This is local synthetic evidence, not proof of a deployed ADF or a scientific result.")
    : selected.status === "stale" ? "Prior evidence is no longer current. Inspect the requirement revision and dependency fingerprint, then rerun."
    : selected.kind === "qc" ? "The synthetic output inventory conflicts with the explicit QC context. A real root cause would require original logs and a fixing commit."
    : "The observed fixture value or content differs from the sandbox contract. This local mismatch is demonstrated; a production root cause is not established.";
  const timeline = [
    ...state.runs.map(item => ({time:item.started_at,kind:"run",item})),
    ...state.reviews.map(item => ({time:item.approved_at,kind:"review",item})),
    ...state.parameter_changes.map(item => ({time:item.approved_at,kind:"parameter",item})),
  ].sort((a,b) => b.time.localeCompare(a.time)).map(event => {
    const r = event.item;
    if (event.kind === "run") {
      const status = r.summary.stale ? "stale" : r.summary.fail ? "fail" : "pass";
      return `<div class="timeline-item timeline-${status}"><strong>${r.id === state.latest.id ? "Latest local run / current status" : "Historical local run / recorded status"}</strong><code>${esc(r.id)}</code><small>${esc(r.started_at)} / ${r.duration_ms} ms</small><p>${Object.entries(r.summary).map(([key,count]) => badge(`${count} ${key}`,key)).join(" ")}</p></div>`;
    }
    return `<div class="timeline-item timeline-stale"><strong>${event.kind === "review" ? "Reviewed sandbox patch" : "Approved sandbox requirement revision"}</strong><p>${esc(r.reviewer)} / ${esc(event.time)}</p><code>${esc(r.test_id || r.requirement)}</code>${r.diff ? `<details><summary>Approved diff</summary><pre>${pretty(r.diff)}</pre></details>` : `<p>${r.invalidated_tests.length} results invalidated</p>`}</div>`;
  }).join("");
  return `<article class="card"><div class="actions"><button id="run">Run local checks</button><label for="test-filter">Show cases</label><select id="test-filter"><option value="attention" ${testFilter === "attention" ? "selected" : ""}>Failures &amp; stale evidence</option><option value="qc" ${testFilter === "qc" ? "selected" : ""}>QC controls</option><option value="all" ${testFilter === "all" ? "selected" : ""}>All proposed/local cases</option></select></div>
    <p>${esc(state.scenarios.find(s => s.id === scenario).description)}</p><p class="muted">Latest run <code>${esc(state.latest.id)}</code> &middot; ${esc(state.latest.started_at)} &middot; ${state.latest.duration_ms} ms measured local validation. ${state.test_count} cases; ${state.fixture_event_count} seeded correlated fixture events across all scenarios.</p>
    <div class="test-table scroll"><table><thead><tr><th>Test / variant</th><th>Requirement</th><th>Mode</th><th>Current evidence</th><th>Inspect</th></tr></thead><tbody>
      ${rows.map(r => `<tr class="${r.id === selected.id ? "selected" : ""}"><td>${esc(r.id)}</td><td>${r.requirement}</td><td>${esc(r.execution_mode.replaceAll("_"," "))}</td><td>${badge(r.status)}</td><td><button class="secondary" data-test="${esc(r.id)}">Inspect</button></td></tr>`).join("") || '<tr><td colspan="5">No failures or stale results in this view. Use QC controls to inspect conditional passes.</td></tr>'}
    </tbody></table></div></article>
    <div class="grid"><article class="card"><p class="eyebrow">EVIDENCE-LINKED TRIAGE</p><h3>${esc(selected.id)}</h3>${badge(selected.status)}<p>${esc(selected.execution_mode)} / ${selected.requirement} revision ${selected.requirement_revision}</p>
      <div class="value-grid"><div><h4>Expected contract</h4><pre>${pretty(selected.expected)}</pre></div><div><h4>Recorded observation</h4><pre>${pretty(selected.observed)}</pre></div></div>
      <p>${esc(selected.detail)}</p>${selected.stale_reason ? `<p class="warning">${esc(selected.stale_reason)} Recorded result: ${esc(selected.recorded_status)}</p>` : ""}
      <p class="info"><strong>Hypothesis / inference:</strong> ${esc(hypothesis)}</p>
      <p class="muted">The comment reporting CNV and MSI updates together does not establish a confirmed root cause.</p>
      <div class="actions">${selected.status === "fail" ? `<button id="preview-patch" data-id="${esc(selected.id)}">Preview minimal local patch</button>` : ""}</div>
      <details><summary>Dependency / environment fingerprint</summary><pre>${pretty({fingerprint:selected.fingerprint,dependencies:selected.dependency_hashes,source_revision:selected.source_revision,environment:state.latest.environment})}</pre></details>
      <h4>Supporting source / candidate evidence</h4>${sourceExcerpt(selected.requirement)}</article>
    <article class="card"><h3>Execution &amp; review timeline</h3>${timeline}
      <h4>Conditional controls, not manufactured success</h4><p>CNV failed QC may suppress plots. MSI-QCFail may complete the pipeline while sample/MSI QC still fails. No MAPD boundary is inferred.</p>
      <details><summary>Correlated latest-run assertion events (${state.run_events.length})</summary><pre>${pretty(state.run_events)}</pre></details>
      <p class="warning">Historical run references remain separate. Actual local assertion execution does not imply pipeline execution.</p></article></div>`;
}
function impactView() {
  return `<div class="grid"><article class="card"><p class="eyebrow">SEMANTIC DIFF / HUMAN DECISION</p><h3>A requirement changes. Evidence expires selectively.</h3>
    <p>The real R18 source threshold is <code>0.001</code>. This demonstration proposes <code>0.002</code> only in the selected sandbox contract.</p>
    <pre>- fusion non-targeted normalized read threshold: 0.001\n+ fusion non-targeted normalized read threshold: 0.002\n  scope: DNA+Fusion / RNACountsActor.ini\n  semantic impact: sensitivity policy changed; needs review</pre>
    <p class="info">Retrieved interpretation: R18 also contains the shared annotator decision. Its family revision invalidates both annotator checks plus the Fusion threshold check. Kit, alignment and other requirement evidence remains valid.</p>
    <label for="parameter-reviewer">Sandbox requirement reviewer</label><input id="parameter-reviewer" placeholder="Engineer / presenter name">
    <label class="checkbox"><input type="checkbox" id="parameter-approve"> I approve this synthetic requirement revision, not a real release change.</label>
    <div class="actions"><button id="change-parameter" ${state.contract.fusion_threshold === "0.002" ? "disabled" : ""}>Approve sandbox parameter change</button><button id="go-runner" class="secondary">Inspect evidence &amp; rerun</button></div>
    <p>Current sandbox threshold: <strong>${esc(state.contract.fusion_threshold)}</strong> / R18 revision ${state.contract.revisions.R18}</p>
    ${state.parameter_changes.map(c => `<p class="warning">${esc(c.approved_at)} / ${esc(c.reviewer)}: ${c.invalidated_tests.length} assertions invalidated. The parameter file was not silently updated.</p>`).join("")}</article>
    <article class="card"><h3>Exact supporting excerpt</h3>${sourceExcerpt("R18")}<h4>Proposed tests / inference, not approved acceptance</h4>
    <ul>${state.latest.results.filter(r => r.requirement === "R18").map(r => `<li>${esc(r.id)} ${badge(r.status)}</li>`).join("")}</ul>
    <p class="muted">After approval, the old pass is stale. Rerunning observes a threshold mismatch. Preview, review, apply the precise local patch, and rerun. Original candidate evidence remains unchanged.</p></article></div>`;
}
function exportView() {
  return `<div class="grid"><article class="card"><p class="eyebrow">DRAFT EVIDENCE PACK</p><h3>Export what happened. Keep what is missing.</h3>
    <p>The JSON export preserves this scenario's exact run IDs, assertions, expected/observed values, requirement revisions, file fingerprints, source pins, timestamps, review diffs, historical references, and remaining gaps.</p>
    <div class="actions"><a class="button" id="export-json" href="/api/export?scenario=${esc(scenario)}">Export draft evidence JSON</a><a class="button secondary" href="/api/bundle?scenario=${esc(scenario)}">Build synthetic toy ZIP</a></div>
    <p class="warning">Toy ZIP: NON-INSTALLABLE. No genuine ADF build, installation, instrument run, or released binary MD5 validation.</p>
    <h4>Measured local timings</h4>${state.runs.map(r => `<p><code>${esc(r.id)}</code> &mdash; ${r.duration_ms} ms</p>`).join("")}
    <p>Production savings: <strong>unmeasured</strong>. Planned schedule is not a labor estimate. A pilot must record baseline/assisted labor, elapsed time, review overhead, and defect escapes.</p></article>
    <article class="card"><h3>Remaining gaps</h3><ul>${evidence.limitations.map(l => `<li>${esc(l)}</li>`).join("")}</ul>
    <h4>Future data, not a trained model</h4><p>${evidence.ai_replay.length} interpretation candidates come from one release and need engineer review. No training or generalization scores are reported.</p>
    <p>Future-data schema separates requirement revisions, test executions, and failure/fix/retest episodes. Split by release and time; keep DNA/Fusion relatives together. Future fixes and resolution evidence must not appear in prediction inputs.</p></article>
    <article class="card wide"><h3>Ten actual captured-source checks</h3><p>${esc(state.source_checks.scope)}. Reproduced with the supplied source validator, without modifying its original evidence files.</p>
    <div class="scroll"><table><thead><tr><th>Source check</th><th>Observation</th><th>Scope</th></tr></thead><tbody>${state.source_checks.checks.map(c => `<tr><td>${esc(c.check)}</td><td>${badge(c.result,"pass")}</td><td>${esc(c.scope)}</td></tr>`).join("")}</tbody></table></div></article></div>`;
}
document.addEventListener("click", event => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.tab) { tab = button.dataset.tab; render(); }
  if (button.dataset.requirement) { requirement = button.dataset.requirement; render(); }
  if (button.dataset.test) { selectedTest = button.dataset.test; render(); }
  if (button.id === "go-runner") { tab = "runner"; render(); }
  if (button.id === "run") action(async () => {
    const run = await api("/api/run",{scenario}); await refresh();
    notice(`Run ${run.id} finished in ${run.duration_ms} ms. Local fixture checks only.`);
  });
  if (button.id === "preview-patch") action(async () => {
    proposal = await api("/api/preview",{scenario,test_id:button.dataset.id});
    $("#patch-diff").textContent = proposal.diff; $("#patch-warning").textContent = proposal.warning;
    $("#reviewer").value = ""; $("#approve").checked = false; $("#review-dialog").showModal();
  });
  if (button.id === "cancel-review") $("#review-dialog").close();
  if (button.id === "change-parameter") action(async () => {
    if (!$("#parameter-approve").checked) throw new Error("Review and approve the sandbox requirement revision first.");
    const result = await api("/api/parameter",{scenario,reviewer:$("#parameter-reviewer").value});
    await refresh(); notice(`${result.invalidated_tests.length} R18 results invalidated; unrelated results retained. Rerun to observe the mismatch.`);
  });
  if (button.id === "reset" && window.confirm("Reset all copied fixtures, local runs, patches and sandbox requirement revisions? Original evidence is untouched.")) action(async () => {
    await api("/api/reset",{}); selectedTest = undefined; await refresh(); notice("Synthetic sandbox reset. Original evidence unchanged.");
  });
});
$("#review-form").addEventListener("submit", event => {
  event.preventDefault();
  action(async () => {
    await api("/api/apply",{scenario,proposal_id:proposal.id,reviewer:$("#reviewer").value});
    $("#review-dialog").close(); await refresh();
    notice("Reviewed correction applied only to the copied fixture. Prior evidence is stale until you run local checks again.");
  });
});
$("#scenario").addEventListener("change", event => {
  scenario = event.target.value; selectedTest = undefined; action(refresh);
});
document.addEventListener("change", event => {
  if (event.target.id === "test-filter") { testFilter = event.target.value; render(); }
});
action(async () => { evidence = await api("/api/evidence"); await refresh(); });
