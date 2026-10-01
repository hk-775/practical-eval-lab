# Security

This educational application binds to `127.0.0.1`. It has no user authentication
and is not a hosted multi-user service. Its web API accepts same-origin JSON
writes. Tool calls use in-memory simulations; they cannot access external systems.

The webpage makes no model API calls. The optional command-line OpenAI adapter
sends the chosen dataset inputs to the configured provider and may incur costs.
Keep API keys in your environment, never in cases, profiles, code, or reports.
Candidate exceptions are reported by type without copying provider error bodies.

For a public repository, use GitHub's private vulnerability reporting feature.
The maintainer must enable it before publication. If that channel is unavailable,
request a private reporting channel without posting exploit details or secrets.

Do not report exposed credentials in a public issue. Revoke them through the
provider and contact the maintainer privately.
