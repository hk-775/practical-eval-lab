# Third-party material

The project's original code and synthetic teaching cases use [MIT-0](LICENSE).
The following data retains its own license; MIT-0 does not replace it.

| Material | Source | License | Included notice |
|---|---|---|---|
| 12 human-preference pairs, their conversation context, and reproductions in example reports | Anthropic HH-RLHF, `helpful-base/test.jsonl.gz`, revision `c72f5cee8eb7b4d2ea5617657f4430d5e333af07` | MIT, copyright (c) 2022 Anthropic | [Full MIT notice](eval_lab/data/response_quality/LICENSE.txt) |

The [per-record manifest](eval_lab/data/response_quality/provenance.json) records
source line numbers, SHA-256 hashes, local splits, and A/B mappings. Text and
human preference labels were retained; see the [data provenance explanation](docs/data-provenance.md).
The source repository's [license](https://github.com/anthropics/hh-rlhf/blob/c72f5cee8eb7b4d2ea5617657f4430d5e333af07/LICENSE)
and [dataset description](https://github.com/anthropics/hh-rlhf/blob/c72f5cee8eb7b4d2ea5617657f4430d5e333af07/README.md)
were checked when selecting this sample.

Dependencies have their own licenses and are recorded in `uv.lock`. No external
fonts, analytics scripts, image libraries, customer traces, or production data
are bundled.
