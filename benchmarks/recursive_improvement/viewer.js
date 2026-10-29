(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("evidence").textContent);
  const byId = id => document.getElementById(id);
  const seed = byId("seed"), arm = byId("arm");
  let generation = 0;
  arm.value = "recursive_optimizer";
  function show() {
    const run = data.runs.find(row => row.seed === Number(seed.value) && row.arm === arm.value);
    generation = Math.min(generation, run.checkpoints.length - 1);
    const checkpoint = run.checkpoints[generation];
    byId("position").textContent = `Generation ${generation} of ${run.checkpoints.length - 1}`;
    byId("checkpoint").textContent =
      `Development: ${checkpoint.development.task_success}/${checkpoint.development.episodes}. ` +
      `Validation: ${checkpoint.validation.task_success}/${checkpoint.validation.episodes}. ` +
      `Validation-selected generation: ${run.selected_generation}.`;
    byId("policy").textContent = JSON.stringify(checkpoint.artifact.policy, null, 2);
    byId("optimizer").textContent = JSON.stringify(checkpoint.artifact.optimizer, null, 2);
    const history = run.history.find(row => row.generation === generation);
    byId("proposals").textContent = history ? JSON.stringify(history.trials.map(trial => ({
      slot: trial.slot,
      accepted: trial.accepted,
      changes: trial.changes,
      strategy_used: trial.proposal.strategy_used,
      diagnosis: trial.proposal.diagnosis,
      correct_development_episodes: trial.development.task_success,
      provider_calls: trial.development.provider_calls,
      preserves_previous_successes: trial.preserves_previous_successes
    })), null, 2) : "Starting configuration. No edits have been proposed.";
    byId("previous").disabled = generation === 0;
    byId("next").disabled = generation === run.checkpoints.length - 1;
  }
  seed.addEventListener("change", () => { generation = 0; show(); });
  arm.addEventListener("change", () => { generation = 0; show(); });
  byId("previous").addEventListener("click", () => { generation--; show(); });
  byId("next").addEventListener("click", () => { generation++; show(); });
  byId("controls").hidden = false;
  byId("inspection").hidden = false;
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
