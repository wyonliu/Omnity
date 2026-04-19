# OmeBench

Reproducible long-context memory benchmark for the Personal Harness Runtime.

- `sample_corpus/` — tiny fixture (two interviews + one journal + one facts
  file). Used by the test suite.
- `sample_questions.jsonl` — 5 questions across categories (single-hop,
  temporal, multi-hop, forbid).
- See `packages/mindos/src/mindos/harness/omebench/` for the driver code.

## Quick run

```bash
python -m mindos.harness.omebench.cli \
    --corpus    packages/mindos/omebench/sample_corpus \
    --questions packages/mindos/omebench/sample_questions.jsonl \
    --backend   stub
```

## Public board (target)

We will publish a public OmeBench v0 score when W6 lands on the Captain's
personal corpus: 53 interviews + year of Journal entries + Longfor Qianding
strategy notes. Until then every number here is from sample fixtures only —
do not cite.

## Scoring

Rule-based by default. No LLM-judge is shipped, so every score is
deterministic and reproducible. Rubrics per question:

| field | semantics |
|---|---|
| `expected_contains` | all substrings (case-insensitive) must appear |
| `expected_any` | at least one substring must appear |
| `expected_regex` | all regexes must match |
| `forbid_contains` | any listed substring → hard fail |

A question with no rubric counts as pass if the response is non-empty.

## Why OmeBench exists

LoCoMo measures long-conversation QA. OmeBench measures **long-life QA**:
mixed-type memories (episode / fact / skill), mixed-modality rubrics
(substring / regex / forbid), and **authored** corpora instead of
synthesized dialogues. The numbers are comparable within OmeBench; they
should NOT be compared to LoCoMo directly.
