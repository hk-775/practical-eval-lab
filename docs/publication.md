# Publication inventory

## Current identity

- Project: Practical Eval Lab
- Repository: `hk-775/practical-eval-lab`
- Distribution: source repository, buildable wheel/sdist, local Python webpage, command-line runner
- License: MIT No Attribution (`MIT-0`), selected by the owner
- Status: public source repository; publication approved by the owner
- Default branch: `main`
- Current visibility: public as of October 1, 2026
- Publication channel: [GitHub source repository](https://github.com/hk-775/practical-eval-lab)
- No public hosted application, package release, or cloud deployment is implied

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

## Architecture decision

**AWS services reference architecture: not applicable.**

This project's intended platform is a local Python development environment with
GitHub source distribution. There is no AWS integration, IaC, deployment target,
or hosted execution service. Inventing cloud services would misrepresent the
implementation. Revisit this decision if a hosted runner is actually designed.

The local HTTP server has no authentication or multi-user isolation. Publishing
its source does not authorize exposing it as an internet service. A future static
GitHub Pages preview would need an explicitly labeled demo mode; the current
webpage requires its local Python API.

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
- CI uses GitHub-hosted runners and read-only workflow tokens. No deployment
  environments, hosted Pages site, or release assets were present at publication.
- The owner confirmed external approval and authorized public visibility on
  October 1, 2026. Approval receipts remain in ignored local state.

No GitHub Release, registry upload, or paid service is part of this milestone.
