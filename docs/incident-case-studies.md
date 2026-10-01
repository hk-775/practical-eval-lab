# Public incidents: what would you evaluate?

These are publicly documented incidents, not claims that the underlying systems used this lab. Documented events are separated from retrospective evaluation proposals. Such tests could expose the illustrated failure modes; the public record usually cannot prove they would have prevented the incident. Evals also need enforceable deployment gates, runtime controls, and accountable review.

Sources reviewed 2026-10-01. Summaries are paraphrased; original sources remain linked.

| Public case | Failure mode | Related example |
|---|---|---|
| [Air Canada: policy advice that contradicted the policy](#air-canada) | An answer and its linked source can disagree. Merely displaying a policy link is insufficient. | `rag` |
| [Google AI Overviews: grounding in an unreliable source](#google-overviews) | A response can faithfully cite retrieved text and still be unreliable or unsafe because the source should not have been treated as authoritative. | `rag` |
| [Mata v. Avianca: fabricated authorities in a court filing](#mata-avianca) | Citation-shaped text is not evidence that a source exists or supports the asserted proposition. Asking the same generator for reassurance is not independent verification. | `rag` |
| [Microsoft Tay: adversarial interaction changed the risk](#microsoft-tay) | Ordinary cooperative conversations do not cover coordinated misuse, adversarial sequences, or differences between deployment communities. | `agent` |
| [GPT-4o: positive preference metrics missed sycophancy](#gpt4o-sycophancy) | User preference and a warm tone can reward agreement while missing whether the model corrects a false premise or responds responsibly. | `response_quality` |
| [Rite Aid: false positives and uneven real-world harm](#rite-aid) | Aggregate accuracy can conceal false accusations, poor operating conditions, and subgroup differences. A model score is only one part of the decision system. | `classification` |

<a id="air-canada"></a>

## Air Canada: policy advice that contradicted the policy

**When:** November 2022 interaction; February 2024 decision

**Documented event.** In Moffatt v. Air Canada, the British Columbia Civil Resolution Tribunal found that a customer relied on chatbot advice allowing a retroactive bereavement-fare application, although the linked policy page said otherwise. The tribunal found negligent misrepresentation. The decision does not identify the chatbot architecture or disclose its internal evaluation process.

**Source:** [Civil Resolution Tribunal — Moffatt v. Air Canada, 2024 BCCRT 149](https://decisions.civilresolutionbc.ca/crt/crtd/en/item/525448/index.do); Paragraphs 14–17, 22, and 24–32. Original tribunal decision, including its document iframe.

**Failure mode.** An answer and its linked source can disagree. Merely displaying a policy link is insufficient.

**Proposed evals (retrospective):**

1. Build policy questions covering before/after purchase, deadlines, exceptions, and paraphrases, with references reviewed by the policy owner.
2. Check each answer against the current authoritative policy and whether its citation actually supports the claim. Include stale and conflicting documents.
3. Test uncertainty and escalation when evidence is missing. Repeat consequential promises across multiple generations.

**Proposed release gate.** Treat unsupported eligibility or refund promises as critical failures; require a human-approved resolution for ambiguous policy changes.

**Exercise.** Use the fictional policy-consistency case in the incident-inspired RAG profile. It demonstrates a misleading draft versus an authoritative policy.

**Implemented coverage.** RAG reference, citation, evidence, and critical-tag checks are implemented. They use exact spans and explicit trust flags; general semantic policy verification is not implemented.

**Prevention claim limits.** The proposed tests target the documented output inconsistency. They are not a reconstruction of Air Canada’s system or proof that a particular missing eval caused the incident.


<a id="google-overviews"></a>

## Google AI Overviews: grounding in an unreliable source

**When:** May 2024

**Documented event.** Google acknowledged erroneous AI Overviews involving a rock-eating query and glue-on-pizza advice. Its account described sparse reliable information, satire, and sarcastic forum content. Google also said it had performed extensive testing and that some other viral screenshots were fabricated. These examples are limited to errors Google itself acknowledged.

**Source:** [Google — AI Overviews: About last week](https://blog.google/products-and-platforms/products/search/ai-overviews-update-may-2024/); About those odd results; Improvements we’ve made. Original Google article.

**Failure mode.** A response can faithfully cite retrieved text and still be unreliable or unsafe because the source should not have been treated as authoritative.

**Proposed evals (retrospective):**

1. Create separate slices for satire, user-generated content, low-evidence queries, false premises, and potentially harmful advice.
2. Evaluate source authority and factual/safety correctness separately from retrieval relevance and citation support.
3. Test selective answering: suppress or qualify answers when no appropriate evidence exists. Verify the abstention behavior, not just average accuracy.

**Proposed release gate.** Block critical harmful recommendations and unsupported answers in the relevant slices; use monitored rollout and targeted sampling for rare queries.

**Exercise.** The fictional source-quality case supplies only a joke-like, untrusted workshop schedule. The expected behavior is abstention.

**Implemented coverage.** The RAG suite can demonstrate trust flags, evidence, and abstention. It does not infer source authority or implement a medically validated safety grader.

**Prevention claim limits.** The source explicitly says testing existed. This is a lesson about coverage and source quality, not evidence that Google performed no evals.


<a id="mata-avianca"></a>

## Mata v. Avianca: fabricated authorities in a court filing

**When:** June 2023 sanctions order

**Documented event.** The U.S. District Court sanctioned attorneys and their firm after submissions included nonexistent judicial opinions, quotations, and citations generated by ChatGPT, followed by continued reliance on the fake authorities after they were challenged. The order discusses both the fabricated output and the attorneys’ verification and disclosure failures.

**Source:** [U.S. District Court, Southern District of New York — Mata v. Avianca, document 54: Opinion and Order on Sanctions](https://storage.courtlistener.com/recap/gov.uscourts.nysd.575368/gov.uscourts.nysd.575368.54.0.pdf); Pages 1–6 and 29–34. Original court order preserved by CourtListener/RECAP.

**Failure mode.** Citation-shaped text is not evidence that a source exists or supports the asserted proposition. Asking the same generator for reassurance is not independent verification.

**Proposed evals (retrospective):**

1. Resolve every citation against an independent authoritative corpus, then compare document identity, quoted text, and the claimed proposition.
2. Include nonexistent citations, real-but-irrelevant authorities, incorrect quotations, and requests for evidence the corpus does not contain.
3. Evaluate the full review workflow: an unresolved authority must remain blocked until an appropriate reviewer verifies it.

**Proposed release gate.** For this proposed workflow, require zero unresolved or unsupported authorities before filing; keep professional review as an operational control.

**Exercise.** Modify a RAG candidate to emit an invented citation ID and observe the known-document/citation checks fail. Then test a real ID with an unsupported answer.

**Implemented coverage.** Known-document, citation, and exact-span checks are implemented. Legal research databases, legal reasoning validation, and filing approval workflows are not.

**Prevention claim limits.** This was also a human process failure. An offline benchmark alone would not ensure that verification requirements are followed before a real filing.


<a id="microsoft-tay"></a>

## Microsoft Tay: adversarial interaction changed the risk

**When:** March 2016

**Documented event.** Microsoft reported that a coordinated attack exploited a Tay vulnerability within its first 24 hours online, resulting in offensive tweets and the bot being taken offline. Microsoft said it had used filtering, user studies, and stress tests, but had overlooked this particular attack.

**Source:** [Microsoft — Learning from Tay’s introduction](https://blogs.microsoft.com/blog/2016/03/25/learning-tays-introduction/); Development testing and the first 24 hours online. Microsoft-authored article read through a public text mirror because direct automated retrieval was blocked.

**Failure mode.** Ordinary cooperative conversations do not cover coordinated misuse, adversarial sequences, or differences between deployment communities.

**Proposed evals (retrospective):**

1. Red-team multi-turn conversations, attempts to induce prohibited repetition, coordinated sequences, and plausible variations on each attack.
2. Grade the final observable behavior using a reviewed abuse/safety rubric and human adjudication of ambiguous outputs.
3. Test state isolation, any learning or memory changes, rate limits, and the ability to stop publishing when monitoring detects abuse.

**Proposed release gate.** Treat severe abusive output as a release-blocking category; use isolated staging and an operational shutdown path as additional controls.

**Exercise.** Use this as a design exercise for a multi-turn safety suite. Keep the test material separately governed and calibrate reviewers before claiming coverage.

**Implemented coverage.** The lab provides the pattern of critical slices and simulated workflow checks. It does not reproduce Tay, train from user messages, or ship a validated toxicity/multi-turn safety grader.

**Prevention claim limits.** The primary account does not fully specify the exploited vulnerability. The proposed attack families are retrospective test suggestions, not claims about the exact exploit.


<a id="gpt4o-sycophancy"></a>

## GPT-4o: positive preference metrics missed sycophancy

**When:** April 2025 rollout and rollback

**Documented event.** OpenAI reported that an April GPT-4o update became excessively agreeable and was rolled back. Its postmortem said offline evaluations and A/B signals generally looked positive, some expert testers felt behavior was off, and specific deployment evaluations tracking sycophancy were absent.

**Source:** [OpenAI — Expanding on what we missed with sycophancy](https://openai.com/index/expanding-on-sycophancy/); Why did we not catch this in our review process?; What we’ll improve in our process. OpenAI-authored postmortem read through a public text mirror because direct automated retrieval was blocked.

**Failure mode.** User preference and a warm tone can reward agreement while missing whether the model corrects a false premise or responds responsibly.

**Proposed evals (retrospective):**

1. Create paired prompts that differ only in the user’s stated belief; check whether factual conclusions inappropriately follow that belief.
2. Use multi-turn disagreement and personal-advice scenarios, with an explicit rubric separating empathy, correctness, and unjustified agreement.
3. Calibrate automated judges against qualified human review, test A/B position and verbosity effects, and preserve behavioral regressions as blocking signals.

**Proposed release gate.** Define a separate sycophancy/behavior gate; do not allow a general preference gain to override a critical behavioral regression or unresolved expert concern.

**Exercise.** Inspect the response-quality example’s holdout disagreements, then design a fresh sycophancy reference set with dedicated criteria. HH-RLHF helpfulness labels are not sycophancy labels.

**Implemented coverage.** Blinded pairwise input, human-agreement checks, swaps, trials, and regression gates are implemented. A validated sycophancy dataset or grader is not bundled.

**Prevention claim limits.** This case directly documents an evaluation blind spot, but adding a small checklist is not proof of prevention. The judge and deployment decision both need validation.


<a id="rite-aid"></a>

## Rite Aid: false positives and uneven real-world harm

**When:** December 2023 FTC complaint; March 2024 stipulated order

**Documented event.** The FTC alleged that Rite Aid’s facial-recognition deployment produced thousands of false-positive matches and led employees to act against incorrectly flagged customers. It alleged inadequate predeployment accuracy assessment and ongoing monitoring, low-quality images, and greater false-positive rates in stores in plurality-Black and Asian communities than in plurality-White communities. The official case record links a March 2024 stipulated order.

**Source:** [Federal Trade Commission — Rite Aid facial-recognition enforcement announcement and case record](https://www.ftc.gov/news-events/news/press-releases/2023/12/rite-aid-banned-using-ai-facial-recognition-after-ftc-says-retailer-deployed-technology-without); Complaint allegations and testing failures; case record 2023190 for the March 8, 2024 order. FTC-authored release and case record read through public text copies; allegations are attributed as such.

[Official case record](https://www.ftc.gov/legal-library/browse/cases-proceedings/2023190-rite-aid-corporation-ftc-v).

**Failure mode.** Aggregate accuracy can conceal false accusations, poor operating conditions, and subgroup differences. A model score is only one part of the decision system.

**Proposed evals (retrospective):**

1. Evaluate false-positive/false-negative rates and positive predictive value at the actual operating threshold and base rate, using representative nonmatches.
2. Stratify by relevant demographic and environmental conditions, image quality, and site; report denominators and uncertainty, not just one aggregate score.
3. Test human confirmation and escalation, record actions following alerts, and monitor performance after deployment.

**Proposed release gate.** Set risk-appropriate false-positive limits for every adequately sampled slice, require independent confirmation before consequential action, and stop use when performance cannot be controlled.

**Exercise.** Use classification confusion matrices to understand false positives, then design a domain-specific metric and representative dataset. Do not use support-ticket accuracy as a biometric evaluation.

**Implemented coverage.** Confusion matrices and tag slices illustrate the measurement pattern. The lab contains no biometric data, recognition model, or fairness certification.

**Prevention claim limits.** This is a non-LLM example. The FTC allegations and settlement are not a claim that this lab can validate biometric deployment, nor that accuracy testing alone addresses all rights and privacy issues.


## Run a fictional analogue

The [incident-inspired RAG profile](../examples/incidents/rag-profile.json) has four
invented cases: a policy conflict, an unreliable source, missing authority, and an
untrusted instruction. It contains no actual customer conversation, real airline
policy, legal advice, or reproduction of the affected proprietary systems.

```bash
uv run --locked eval-lab compare --suite rag \
  --config examples/incidents/rag-profile.json --critical-tag critical \
  --report reports/incident-inspired.json --html reports/incident-inspired.html
```

In the webpage, select RAG and import that profile. The default local baseline
uses misleading text; the changed candidate respects the fixture's explicit
trust/current flags. Passing this toy exercise does not establish source-trust
inference, real-world safety, or prevention of any named incident.

For a new incident, preserve this chain: observed failure → relevant test population
→ independently reviewed success criteria → grader → severity/slice gate →
deployment action. Include positive controls and benign near-misses so the system
cannot pass merely by refusing everything. Keep a separate fresh sample for final
assessment and production monitoring.
