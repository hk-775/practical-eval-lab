"use strict";
(() => {
  const report = JSON.parse(document.getElementById("report").textContent);
  const profile = document.getElementById("profile");
  const episode = document.getElementById("episode");
  const previous = document.getElementById("previous");
  const next = document.getElementById("next");
  const motion = document.getElementById("motion");
  const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let step = 0;
  let paused = false;
  let visible = true;
  const labels = {unrestricted: "Unrestricted", permissions: "Permissions",
    invariants: "Business invariants", deny_all: "Deny all"};
  const text = (id, value) => { document.getElementById(id).textContent = value; };
  const json = (id, value) => text(id, JSON.stringify(value, null, 2));
  function motionState() {
    const reduced = preference.matches;
    document.body.classList.toggle("motion-ready", !reduced);
    document.body.classList.toggle("motion-paused", paused || document.hidden || !visible);
    motion.disabled = reduced;
    motion.textContent = paused ? "Resume motion" : "Pause motion";
    motion.setAttribute("aria-pressed", String(paused));
    text("motion-status", reduced ? "Static view: reduced-motion preference is enabled." :
      paused ? "Illustrative motion paused." : "Illustrative flow; recorded steps advance with the controls below.");
  }
  for (const name of Object.keys(report.configurations)) {
    profile.add(new Option(labels[name], name));
  }
  if (report.configurations.permissions) profile.value = "permissions";
  function render() {
    const item = report.configurations[profile.value].episodes[Number(episode.value)];
    const row = item.trace[step];
    text("episode-title", item.condition.replaceAll("_", " "));
    text("outcome", `Correct handling: ${item.outcome.task_success ? "yes" : "no"}. ` +
      `Business completed: ${item.outcome.business_completed ? "yes" : "no"}. ` +
      `Unsafe effects: ${item.outcome.unsafe_effects}. Terminal: ${item.outcome.terminal}.`);
    text("position", `Step ${step + 1} of ${item.trace.length}`);
    json("proposal", row.plan);
    json("feedback", row.result);
    json("effects", row.new_effects.length ? row.new_effects : "No tool mutation committed at this step.");
    json("final", item.outcome);
    previous.disabled = step === 0;
    next.disabled = step === item.trace.length - 1;
  }
  function options() {
    const old = episode.selectedOptions[0]?.dataset.caseId;
    episode.replaceChildren();
    report.configurations[profile.value].episodes.forEach((item, index) => {
      const option = new Option(item.case_id, String(index));
      option.dataset.caseId = item.case_id;
      episode.add(option);
      if (item.case_id === old || (!old && item.condition === "early_access_revocation" &&
          item.case_id.endsWith("-0"))) episode.value = String(index);
    });
    step = 0;
    render();
  }
  profile.addEventListener("change", options);
  episode.addEventListener("change", () => { step = 0; render(); });
  previous.addEventListener("click", () => { step -= 1; render(); });
  next.addEventListener("click", () => { step += 1; render(); });
  motion.addEventListener("click", () => { paused = !paused; motionState(); });
  preference.addEventListener("change", motionState);
  document.addEventListener("visibilitychange", motionState);
  new IntersectionObserver(entries => {
    visible = entries[0].isIntersecting;
    motionState();
  }).observe(document.querySelector(".diagram-scroll"));
  document.getElementById("controls").hidden = false;
  motion.hidden = false;
  options();
  motionState();
})();
