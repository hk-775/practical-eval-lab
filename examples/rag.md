# RAG: retrieval, answers, and evidence are different tests

**Task.** Given a question and a small policy library, retrieve document IDs,
quote one answer sentence, and cite it. Return null and empty lists when the
library cannot answer. Each document has explicit `trusted` and `current` flags.

```bash
uv run --locked eval-lab compare --suite rag --html reports/rag.html
uv run --locked eval-lab compare --suite rag --split holdout
```

Development is 2/8 → 8/8. The baseline uses the first overlapping document and its
first sentence. The change ranks lexical overlap using inverse document frequency,
filters stale/untrusted documents, and chooses a matching sentence. Holdout stays
at 1/4: paraphrases, multiple required sources, and conflicting authority remain
unresolved. The holdout command is expected to fail the default gate.

**Why these measurements?** Retrieval recall checks the labeled relevant IDs.
Answer correctness uses exact reference equality. Citation checks require cited
IDs to have been retrieved and be relevant. Evidence checks require the full
answer to be an exact span in each current, trusted cited document. Unanswerable
cases test abstention; a missing answer is not automatically a safe success.

**Limits.** This is extractive RAG. Exact spans are a deliberately narrow evidence
proxy, not semantic entailment or factual truth. A false source can still contain
an exact matching sentence. Real systems need source-quality decisions, factuality
review, semantic grounding, and suitable domain references. The trust flags are
fixture inputs, not a learned source-trust classifier. Retrieval recall for an
unanswerable case is defined here as 1 only when nothing is retrieved; it is not
a universal retrieval convention.

**Try it.** Replace a question with a paraphrase without changing its reference.
Then add a second relevant document. Inspect which checks fail separately. Connect
your own retriever through the Python or HTTP adapter using the documented output
shape; it receives input documents and question, never the expected answer.

[Recorded experiments](results/README.md) · [Dataset](../eval_lab/data/rag)
