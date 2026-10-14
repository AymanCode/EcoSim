# EcoSim: Ayman's product intent

Clarified in Ayman's October 13, 2026 conversation; propagated October 14, 2026.
These are product priorities and decision boundaries, not a simulation implementation change or a claim about current model accuracy.
Quoted excerpts retain Ayman's words with spelling, grammar, capitalization, and punctuation cleanup only; the development guidance below is an operational interpretation.

## Ayman's words

> You want to see how lower taxes would affect the economy as a whole? Try EcoSim and see. You want to see how free healthcare would affect the economy? Try EcoSim. That was the premise of EcoSim.

> You would want to see how lower taxes affect the economy. You can see the macro side, such as GDP. Then you can also see the micro side, like how consumers work and how they are being affected versus businesses as well.

> I would say it's a mix of GDP increase and happiness increase. Finding the medium between both would probably be the best thing.

> Also, things like unemployment and other criteria not being fulfilled, like housing, also contribute to happiness, so it's kind of an abstraction of everything else, while GDP is a metric of measuring output, so you get the mix of both.

> Well, dimming down the agent logic was never part of the discussion, so no, I wouldn't accept that then.

## Development guidance

- **Purpose:** help people understand economic policy through experiments and context, connecting a change such as lower taxes or healthcare provision to its consequences inside the simulation. Show the macro picture alongside effects on consumers/households and businesses.
- **LLM government:** this was a later extension to explore how well an AI can manage an economy. Evaluate output and human wellbeing together, including unemployment, housing, and unmet needs. Ayman has not specified equal weights or approved a composite score; do not invent one or force happiness and GDP to rise together.
- **Model limits:** EcoSim is an abstraction for understanding economic mechanisms, not a one-to-one replica, real-world forecast, or proof of what a policy or AI would do in reality. Explain assumptions that affect interpretation and distinguish desired behavior from verified implemented behavior.
- **Preserve agent behavior:** routine backend improvements are usually fine, but reducing agent logic, decision/update frequency, or modeled behavior for speed requires prior discussion and agreement. A “quick exploration” label does not supply that agreement. The rejection concerns an unagreed simplification, not a permanent ban on every approximation; it does not authorize a rollback or other code change now.
- **Performance evidence:** explain which work an optimization removes and whether agents still make the same decisions at the same frequency. Compare equivalent workloads and settings before claiming a speedup; disclose any agreed approximation and its consequence.
- **Design and decisions:** smoothness without lag is the main aesthetic priority; generic style prescriptions are suggestions. Show/discuss new UI/UX changes and get Ayman's decision before implementing them; explicit direction counts. Preserve accessibility and correctness.
- **Delivery:** surface meaningful choices and assumptions as they arise, with what, why, how, benefits, and costs in roughly three or four concise plain-language sentences, up to three short body paragraphs. No intro, conclusion, code dump, or bare implementation identifiers unless requested. Do not rely on Ayman reading code to discover decisions.

This guidance complements the repository's economic-agent rules and approved proposals; it does not silently revise their equations, tick order, or acceptance criteria. Resolve a material conflict with Ayman before changing modeled behavior.
