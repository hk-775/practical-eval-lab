/* GitHub Pages reads only the explicitly published recordings. No server API,
   execution, credentials, browser storage, or persistence is available here. */
(() => {
  "use strict";
  if (document.documentElement.dataset.mode !== "public") return;
  const base = new URL(".", location.href);
  const jsonCache = new Map();
  async function asset(path, type = "json") {
    const url = new URL(path, base);
    if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname) ||
        !/^\/?(?:samples|reports)\//.test(path)) {
      throw new Error("Only published report assets can be opened.");
    }
    const response = await fetch(url, {credentials: "omit", mode: "same-origin"});
    if (!response.ok) throw new Error(`Recording unavailable (${response.status}). Please reload the page.`);
    return type === "json" ? response.json() : response.text();
  }
  async function cached(path) {
    if (!jsonCache.has(path)) jsonCache.set(path, asset(path).catch(error => {
      jsonCache.delete(path);
      throw error;
    }));
    return structuredClone(await jsonCache.get(path));
  }
  const catalog = () => cached(document.documentElement.dataset.catalog);
  async function recording(suite, split = "dev") {
    const item = (await catalog()).recordings[suite]?.[split];
    if (!item) throw new Error("Choose a published suite and dataset.");
    return {item, report: await cached(item.json)};
  }
  function profile(report) {
    return {schema_version: 2, suite: report.suite, threshold: report.threshold,
      settings: report.settings,
      cases: report.results.map(({case_id, input, expected, tags}) => ({id: case_id, input, expected, tags}))};
  }
  window.EvalLabPublic = Object.freeze({
    async request(path, data) {
      const route = new URL(path, "https://recorded.invalid/");
      const suite = data?.suite || route.searchParams.get("suite") || "classification";
      if (route.pathname === "/suites") return {suites: (await catalog()).suites};
      if (route.pathname === "/candidates") return {candidates: [
        {name: "baseline", kind: "recorded local rules"}, {name: "improved", kind: "recorded local rules"},
      ]};
      if (route.pathname === "/config") {
        const {report} = await recording(suite);
        return {config: profile(report.after), revision: "recorded", saved: false};
      }
      if (route.pathname === "/runs") return {runs: []};
      if (route.pathname === "/compare" || route.pathname === "/run") {
        const {report} = await recording(suite, data.split);
        if (route.pathname === "/compare") return report;
        if (!["baseline", "improved"].includes(data.candidate)) throw new Error("Choose a recorded candidate.");
        return data.candidate === "baseline" ? report.before : report.after;
      }
      if (route.pathname === "/export-html") {
        const selected = data.report.after || data.report;
        const {item} = await recording(selected.suite, selected.split);
        const key = data.report.after ? "comparison" : selected.candidate.name;
        if (!Object.hasOwn(item.html, key)) throw new Error("This report has no published HTML export.");
        return {html: await asset(item.html[key], "text")};
      }
      throw new Error("To edit cases, run candidates, or save experiments, start the local Python lab.");
    },
  });
})();
