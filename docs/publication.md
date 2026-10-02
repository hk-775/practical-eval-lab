# Publication inventory

## Current identity

- Project: Practical Eval Lab
- Repository: `hk-775/practical-eval-lab`
- Distribution: source repository, GitHub Pages documentation and recorded-results viewer,
  buildable wheel/sdist, local Python webpage, command-line runner
- License: MIT No Attribution (`MIT-0`), selected by the owner
- Status: public source repository; publication approved by the owner
- Default branch: `main`
- Current visibility: public as of October 1, 2026
- Publication channel: [GitHub source repository](https://github.com/hk-775/practical-eval-lab)
- Website: [GitHub Pages](https://hk-775.github.io/practical-eval-lab/)
- The public website serves static documentation and recorded evidence. Candidate
  execution and tuning run in the local Python application.

## Included artifacts

- Six examples, 114 synthetic cases and 12 attributed human-preference pairs
- Deterministic graders, per-check metrics, trace replay, repeated trials, and usage metadata
- Local baseline and improved candidate for each suite
- Optional OpenAI adapter through the CLI (not exercised with live calls)
- Named Python/HTTP candidates and optional CLI model judging
- Versioned webpage profiles, matched comparisons, JSON/HTML reports, and saved-run history
- Regression, critical-case, and slice gates; explicit configuration/execution exit codes
- Locked Python dependencies, unit/API tests, and a real-browser CI check
- Six walkthroughs, recorded offline results, source-cited public incident case studies
- Quickstart, contracts, integration/provenance guides, community documents
- Logical architecture: editable draw.io source and rendered SVG
- Static website generated from the canonical webpage and source guides, with
  report downloads, mobile/browser checks, and a GitHub Pages deployment workflow
- A separate source-checkout decision-model benchmark with frozen synthetic
  calibration/holdout groups, pinned Strands and Laya adapters, and optional Jev.
  Its heavyweight runtime has a separate uv lockfile. The website publishes its
  methodology and reviewed local model recordings; it does not download weights
  or execute models in the browser.

## Architecture decision

**AWS services reference architecture: not applicable.**

This project's platforms are a local Python development environment and a static
GitHub Pages website. There is no AWS integration, IaC, deployment target, or
hosted execution service. Inventing AWS services would misrepresent the
implementation. Revisit this decision if a hosted runner is actually designed.

The local HTTP server has no authentication or multi-user isolation. Publishing
its source does not authorize exposing it as an internet service. GitHub Pages
uses a separate, explicitly labeled recorded-results mode of the same frontend.
It loads only static published assets and does not execute or persist evals.
See [hosting](hosting.md) for the build, network boundaries, and deployment.

## Provenance

The code extends the owner's existing eval-starter project. Added datasets are
synthetic examples authored for the lab, plus a 12-pair Anthropic HH-RLHF sample
under its original MIT license. The source revision, line numbers, record hashes,
transformation, and full notice are included. See `THIRD_PARTY_NOTICES.md`. No
external fonts, customer traces, or runtime production data are bundled. The favicon and original
styles are inherited from the starter. Dependencies are resolved in `uv.lock`.

## Publication checks

- License selected by the owner: MIT-0; canonical text sourced from SPDX.
- Public author identity: the repository owner’s public GitHub identity and noreply email.
- Locked installation, core/API tests, CLI checks, and six-suite browser checks
  are automated. Wheel/sdist checks install outside the source checkout.
- CI targets Python 3.10 and 3.14 on Ubuntu and Python 3.13 on Ubuntu, Windows, and macOS;
  Chromium checks run on Ubuntu. Review each actual run before claiming success.
- Gitleaks scanned the staged source, all reachable Git history, and existing
  GitHub workflow logs before publication. No secrets were detected. No
  pre-existing history was imported from another repository.
- Runtime profiles, reports, environment files, and caches are ignored by Git.
- Private vulnerability reporting, secret scanning, and secret-scanning push
  protection are enabled.
- CI uses GitHub-hosted runners and read-only workflow tokens. Only the Pages
  deployment job gets Pages write and OIDC permissions, scoped to its
  `github-pages` environment and `main` deployment branch.
- The owner confirmed external approval and authorized public visibility on
  October 1, 2026. Approval receipts remain in ignored local state.

No GitHub Release, registry upload, or paid service is part of this milestone.
