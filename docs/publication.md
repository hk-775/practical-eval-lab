# Publication inventory

## Current identity

- Project: Practical Eval Lab
- Repository: `hk-775/practical-eval-lab`
- Distribution: source repository with a local Python webpage and command-line runner
- License: MIT No Attribution (`MIT-0`), selected by the owner
- Status: private remote created; source remains local pending external repository approval
- Default branch: `main`
- Current remote: private and empty
- Intended publication channel: public GitHub source repository after approval
- No public hosted application, package release, or cloud deployment is implied

## Included artifacts

- Three suites, 90 synthetic cases, transparent deterministic graders
- Local baseline and improved candidate for each suite
- Optional OpenAI adapter through the CLI (not exercised with live calls)
- Editable webpage profiles, matched comparisons, import/export, and rollback
- Locked Python dependencies, unit/API tests, and a real-browser CI check
- Quickstart, learning guide, contribution/support/security/conduct documents
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
synthetic examples authored for the lab. No third-party datasets, fonts, images,
customer traces, or runtime production data are bundled. The favicon and original
styles are inherited from the starter. Dependencies are resolved in `uv.lock`.

## Publication checks

- License selected by the owner: MIT-0; canonical text sourced from SPDX.
- Planned public author identity: the repository owner’s GitHub handle and noreply email.
- Clean locked installation, 34 core/API tests, CLI checks, and automated browser
  checks passed locally. GitHub Actions runs the same checks after each push.
- Gitleaks scanned all staged source before the initial commit; no previous commit
  history exists in this new repository. The initial commit is scanned again
  before push.
- Runtime profiles, reports, environment files, and caches are ignored by Git.
- Enable private vulnerability reporting when the repository is made public.
- External repository approval was submitted with reason `1` and is awaiting
  manager action. The submission receipt is kept in ignored local state.

No GitHub Release, registry upload, or paid service is part of this milestone.
