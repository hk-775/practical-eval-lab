(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("evidence").textContent);
  const byId = id => document.getElementById(id);
  const seed = byId("seed"), arm = byId("arm");
  let generation = 0, selected = false;
  arm.value = "recursive_optimizer";
  function show() {
    const run = data.runs.find(row => row.seed === Number(seed.value) && row.arm === arm.value);
    const checkpoint = run.checkpoints[generation];
    const row = selected ? run.archive[run.selected_index] :
      run.archive.find(item => item.artifact_sha256 === checkpoint.artifact_sha256);
    byId("position").textContent = selected ?
      `Selected proposal · generation ${row.generation}, slot ${row.slot ?? "baseline"}` :
      `Generation ${generation} of ${run.checkpoints.length - 1}`;
    byId("checkpoint").textContent =
      `Development ${row.development.task_success}/${row.development.episodes}. ` +
      `Validation ${row.validation.task_success}/${row.validation.episodes}. ` +
      `Accepted as an incumbent: ${row.accepted ? "yes" : "no"}.`;
    byId("policy").textContent = JSON.stringify(row.artifact.policy, null, 2);
    byId("optimizer").textContent = JSON.stringify(row.artifact.optimizer, null, 2);
    byId("proposals").textContent = JSON.stringify({
      artifact: row.artifact_sha256,
      changes: row.changes || [],
      proposal: row.proposal || {method: "starting configuration"},
      development_batch: row.development_batch,
      validation_batch: row.validation_batch
    }, null, 2);
    byId("previous").disabled = generation === 0;
    byId("next").disabled = generation === run.checkpoints.length - 1;
  }
  for (const control of [seed, arm]) control.addEventListener("change", () => {
    generation = 0; selected = false; show();
  });
  byId("previous").addEventListener("click", () => { generation--; selected = false; show(); });
  byId("next").addEventListener("click", () => { generation++; selected = false; show(); });
  byId("selected").addEventListener("click", () => { selected = true; show(); });
  byId("controls").hidden = byId("inspection").hidden = false;
  show();
  const diagram = byId("diagram"), motion = byId("motion");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let paused = false, visible = false;
  function updateMotion() {
    motion.disabled = reduced.matches;
    motion.textContent = reduced.matches ? "Reduced motion" : paused ? "Resume motion" : "Pause motion";
    motion.setAttribute("aria-pressed", String(paused));
    diagram.classList.toggle("running", !paused && visible && !reduced.matches && !document.hidden);
  }
  motion.hidden = false;
  diagram.classList.add("motion-ready");
  motion.addEventListener("click", () => { paused = !paused; updateMotion(); });
  reduced.addEventListener("change", updateMotion);
  document.addEventListener("visibilitychange", updateMotion);
  new IntersectionObserver(entries => { visible = entries[0].isIntersecting; updateMotion(); },
    {threshold: 0.1}).observe(diagram);
  updateMotion();
})();
