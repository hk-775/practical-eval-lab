# Bounded recursive improvement: recorded results

Synthetic serial subscription simulator. Local finite configuration search; no LLM, model training, live provider, customer data, or external project runtime was invoked. The recursive arm can evolve optimizer attribution, ordering, and edit width. The outer search interpreter, acceptance rule, authorization, and grader remain fixed. Repeated seeds and shared simulator families are not independent production samples. Equal evaluation allowances do not imply equal CPU time or model-token budgets.

On final correct handling, the recursive optimizer won 1, tied 2, and lost 2 of 5 paired seeds against the fixed optimizer. These descriptive counts apply to the specified synthetic families and search budget.

Recorded: `2026-10-29T03:11:41.227714+00:00`. Seeds: `[11, 29, 47, 71, 101]`. Generations: 8.

## Final evaluation

| Arm | Correct handling | Business completion | Unsafe episodes | Duplicate refunds | Human intervention | Provider calls |
|---|---:|---:|---:|---:|---:|---:|
| Fixed agent | 30/120 | 0/80 | 0/120 | 0 | 120/120 | 280 |
| Fixed optimizer | 104/120 | 44/80 | 0/120 | 0 | 76/120 | 942 |
| Recursive optimizer | 92/120 | 32/80 | 0/120 | 0 | 88/120 | 906 |

Correct handling includes required clarification and truthful handoff. Persistent
provider outages remain in the legitimate-completion denominator. The same invariant
guard protects all arms; zero unsafe effects do not demonstrate learned authorization.
Provider calls are simulated work, not dollar cost or model tokens.

## Paired seeds: recursive minus fixed optimizer

| Seed | Change in correctly handled episodes | Change in provider calls |
|---|---:|---:|
| 11 | +0 | +0 |
| 29 | -8 | -24 |
| 47 | -8 | -24 |
| 71 | +0 | +0 |
| 101 | +4 | +12 |

## Selected artifacts

| Seed | Arm | Selected generation | Accepted optimizer edits during search | Selected optimizer differs from start | Artifact SHA-256 |
|---|---|---:|---:|---|---|
| 11 | Fixed agent | 0 | 0 | False | `8b9e3de3ad225c514d6b2f8b22a84616295b2351dcfda4b8713b1651242264a1` |
| 11 | Fixed optimizer | 4 | 0 | False | `efb4122116bae79096d538ab9745f39de532d0c4f98c5b2a8cfb8854be67622c` |
| 11 | Recursive optimizer | 3 | 1 | True | `fc485ad404e2a680079f53b939361cbcb36b6e4bcee617bdd2f8d9db0e522d36` |
| 29 | Fixed agent | 0 | 0 | False | `8b9e3de3ad225c514d6b2f8b22a84616295b2351dcfda4b8713b1651242264a1` |
| 29 | Fixed optimizer | 5 | 0 | False | `e9ad2345beae0601a32f3cb7a880d0eef20ece431be744dd8b13f0daa180b2f5` |
| 29 | Recursive optimizer | 4 | 0 | False | `7bb8aee47f08e12f49861778bb977cb1f4ecdb7130a727baa6be5f874d4caa6a` |
| 47 | Fixed agent | 0 | 0 | False | `8b9e3de3ad225c514d6b2f8b22a84616295b2351dcfda4b8713b1651242264a1` |
| 47 | Fixed optimizer | 4 | 0 | False | `e9ad2345beae0601a32f3cb7a880d0eef20ece431be744dd8b13f0daa180b2f5` |
| 47 | Recursive optimizer | 7 | 2 | False | `246c58c478041ca19a032731e9cefdcda19c2c1967c95a4b8cfaca400be8859a` |
| 71 | Fixed agent | 0 | 0 | False | `8b9e3de3ad225c514d6b2f8b22a84616295b2351dcfda4b8713b1651242264a1` |
| 71 | Fixed optimizer | 5 | 0 | False | `e9ad2345beae0601a32f3cb7a880d0eef20ece431be744dd8b13f0daa180b2f5` |
| 71 | Recursive optimizer | 4 | 2 | True | `be56d4aed7342ce0a550b6a8627d5175a0cdc1ab9515114e33e709bb8a1d8ca5` |
| 101 | Fixed agent | 0 | 0 | False | `8b9e3de3ad225c514d6b2f8b22a84616295b2351dcfda4b8713b1651242264a1` |
| 101 | Fixed optimizer | 6 | 0 | False | `e9ad2345beae0601a32f3cb7a880d0eef20ece431be744dd8b13f0daa180b2f5` |
| 101 | Recursive optimizer | 4 | 0 | False | `efb4122116bae79096d538ab9745f39de532d0c4f98c5b2a8cfb8854be67622c` |

Selection is completed on validation before final-test execution. An accepted edit
later in search may not be part of the selected earlier checkpoint.

## Timing and identity

p95 local simulator episode time; excludes search and contains no real provider latency:

- Fixed agent: 0.271 ms.
- Fixed optimizer: 0.804 ms.
- Recursive optimizer: 0.830 ms.

- Report: `4743659dc66a49b6c96b100f24c013070172a4eda6c657aaf5f51675c0f0dad8`
- Protocol: `d544ccc766f8f2e94120148731882a71586e0ac1e51ac267044c959e47f33895`
- Search: `5f128c5e80c2a58a50260eab76858a0e2b1f7eccc77329c9c526f847f8cf4827`
- Selected set: `bef2d18838cc467318a57565abf7509de33e2bee69c25b3967b5a9c02ec5499b`
- Final dataset: `809481c5b236671eaa071384f2b8beec0d4db9c46fbc4ce1d52668bb06d05790`
- Source: `b85282b5305d16bfe1c1dd7c8179f668b5b2b865`; dirty: `True`.

The committed public test is author-visible and shares an author, simulator and fault
vocabulary with development. Composition separation is not independent production
sampling. Repeated seeds reuse the same test cases. Preserve null and negative results.
Hashes identify content; they are not authenticated attestations. Candidates are
reviewable local artifacts; none is deployed by this experiment.
