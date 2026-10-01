# Security

The local server binds to `127.0.0.1` and has no user authentication or multi-user
isolation. It validates loopback Host headers and same-origin JSON writes. Do not
expose it as a public service. Bundled tools are in-memory simulations.

Default candidates run offline. Starting with `--project` enables only the named
Python/HTTP registrations that the local operator supplied. A project file is
trusted executable/network configuration: Python modules execute in-process,
and configured endpoints may call real services or incur costs. A browser request
cannot add a candidate, import arbitrary modules, or select an unregistered URL.
Direct OpenAI registrations are CLI-only.

Keep secrets in environment variables or a secret manager. The HTTP adapter uses
`token_env` for a Bearer token; remote endpoints require HTTPS and redirects are
disabled. Candidate exception messages are omitted because provider errors can
contain private data. Reports still contain application inputs and outputs, model
prompts, and optional response IDs. Review them before sharing; HTML escaping does
not anonymize content. Imported reports are untrusted evidence, not authenticated
measurements.

Versioned tuning profiles contain data, boolean grader settings, and a threshold;
they do not contain executable candidate registrations. Do not connect production
write tools merely to run a teaching example. The runner is sequential, Python
candidates have no forced timeout, and no runtime sandbox is promised for trusted
application code.

Report vulnerabilities through [GitHub's private reporting form](https://github.com/hk-775/practical-eval-lab/security/advisories/new),
which is enabled for this repository. If unavailable, request a private reporting
channel without posting exploit details or secrets. Do not report exposed
credentials in a public issue; revoke them and contact the maintainer privately.
