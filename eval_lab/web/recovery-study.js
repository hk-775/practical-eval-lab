/* Presentation only: no requests, storage, eval execution, or automatic step changes. */
(() => {
  const example = document.querySelector("#recovery-example");
  if (!example) return;
  const cards = [...document.querySelectorAll("#recovery-steps li")];
  const previous = document.querySelector("#recovery-previous");
  const next = document.querySelector("#recovery-next");
  const position = document.querySelector("#recovery-position");
  const motion = document.querySelector("#recovery-motion");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let current = 0;
  let paused = false;

  function show() {
    cards.forEach((card, index) => { card.hidden = index !== current; });
    example.querySelectorAll("[data-flow-step]").forEach(node => {
      node.classList.toggle("active-step", Number(node.dataset.flowStep) === current);
    });
    previous.disabled = current === 0;
    next.disabled = current === cards.length - 1;
    position.textContent = `Step ${current + 1} of ${cards.length}`;
  }
  function updateMotion() {
    example.classList.toggle("motion-enabled", !reduced.matches);
    example.classList.toggle("motion-paused", paused);
    motion.disabled = reduced.matches;
    motion.textContent = reduced.matches ? "Reduced motion" : paused ? "Resume motion" : "Pause motion";
    motion.setAttribute("aria-pressed", String(paused));
  }
  previous.addEventListener("click", () => { current--; show(); });
  next.addEventListener("click", () => { current++; show(); });
  motion.addEventListener("click", () => { paused = !paused; updateMotion(); });
  reduced.addEventListener("change", updateMotion);
  document.querySelector("#recovery-controls").hidden = false;
  motion.hidden = false;
  show();
  updateMotion();
})();
