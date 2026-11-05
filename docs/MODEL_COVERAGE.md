# Learned classifier language coverage
Selection default is **not yet decided**: no model weights or access have been verified.

## Candidate: Llama Prompt Guard 2 86M
Official Meta model card: https://github.com/meta-llama/PurpleLlama/blob/main/Llama-Prompt-Guard-2/86M/MODEL_CARD.md

Meta documents that 86M uses a multilingual base and was trained on English and non-English attack data. Both model sizes were **evaluated** on these eight languages: English, French, German, Hindi, Italian, Portuguese, Spanish, Thai.

**Evaluated coverage != comprehensive guaranteed support.** For a configured language not in this list, label `outside documented evaluation coverage`; for these eight, label `inside documented evaluation coverage`. Code-switching/romanized variants do not have individual documented coverage and must be labeled `not documented`. Record actual tokenizer/model revision, 512-token context segmentation policy and licensing/access status. The HF model ID is `meta-llama/Llama-Prompt-Guard-2-86M` but access must be verified locally.

## Candidate: PIGuard
Paper: https://aclanthology.org/2025.acl-long.1468/ . Verify release revision, model card and language support before selecting it; do not assume multilingual coverage from published effectiveness on English-derived benchmarks.

## Reporting
An experiment record must contain `classifier_coverage_status` for each language/variant and `validated_by_me` for translation review. Never silently promote unvalidated translations to validated evidence.
