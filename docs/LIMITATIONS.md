# Limitations (maintained throughout research)
- Current scaffold does not yet establish any measured defense effectiveness; mock responses are not scored.
- Small single-suite sample and multiple languages yield wide uncertainty intervals.
- Static machine translation may alter attacker intent, formatting and surrounding tool output. Unvalidated variants remain explicitly marked.
- Adaptive search selects languages based on feedback; post-selection language-specific ASR is not a randomized language effect.
- Classifier language support must be documented from each selected model card, including multilingual coverage uncertainty; do not infer coverage from a model's name.
- AgentDojo API changes, model nondeterminism, tokenizer billing, provider behavior and upstream evaluator bugs may constrain exact reproduction.
- An observed failure to attack does not establish security; an observed success does not generalize beyond simulated tasks.
- No real credentials, external targets, or unauthorized tool actions are used.
