# Related work — literature audit (2026-11-05)

| Study | Evidence / overlap | Implication |
| --- | --- | --- |
| AgentDojo (Debenedetti et al., NeurIPS Datasets & Benchmarks 2024) | Simulated tool-using agents, indirect prompt injection, official security and utility checkers. https://github.com/ethz-spylab/agentdojo | Adopt benchmark; no new benchmark claim. |
| BabelDojo (Faerber Lab repository) | Describes multilingual AgentDojo extension, including romanized and code-switched injections. https://github.com/faerber-lab/BabelDojo | Direct conceptual overlap; do not claim multilingual AgentDojo evaluation is novel. |
| AutoDojo (Ma et al., arXiv:2606.15057, 2026) | Adaptive black-box prompt injection against defenses in AgentDojo. https://arxiv.org/abs/2606.15057 | Direct adaptive overlap; C3 is a control, not an invented method. |
| MIPIAD (Muhtadi & Tazwar, arXiv:2605.07269, 2026) | Multilingual indirect injection detection on English/Bangla synthetic examples with classifier and lexical ensembles. https://arxiv.org/abs/2605.07269 | Related to H1 and model-coverage validity, different task substrate. |
| MAPS | Name alone is ambiguous; **bibliographic identity not verified**. Do not attribute unsupported findings. | Verify paper/title/authors before citing formally. |
| AgentShield | This repository name and other similarly named projects are overloaded; local SaaS previously concerned website scanning, not AgentDojo attack robustness. | Describe exact repository and revisions to avoid confusing the project with published claims. |

**Novelty position:** To our knowledge, as of November 2026, the *specific controlled interaction* of language-space adaptive search versus English-only adaptive search on matched AgentDojo tasks remains a question worth replicating; this is **not** a claim that the idea or attack methodology is novel. Verify publication coverage again at final report time.
