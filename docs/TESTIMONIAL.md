# Testimonial capture — script + plan

**Goal:** 1 quote, 20–60 words, from a qualified roboticist (ex-NASA / ex-NVIDIA / active AV or humanoid engineer preferred). Used in demo video punchline and README.

**Deadline:** Day 4 end of day. Day 5 buffer. Do **not** ask Day 6.

## Why this matters

Impact (30% of judging) is the axis where a qualified third-party quote moves the needle most. Judges discount self-pitch; they trust a domain expert who spent 5 minutes with the tool. One good quote can outweigh a dozen polished slides.

## Target list

Rank contacts by: (a) credibility tag judges will recognize, (b) response speed, (c) willingness to go on record.

| Contact | Credibility tag | Priority | Channel |
|---------|-----------------|----------|---------|
| _(fill in — ex-NASA contact)_ | ex-NASA JPL | P0 | WhatsApp / email |
| _(fill in — ex-NVIDIA contact)_ | ex-NVIDIA robotics | P0 | LinkedIn / email |
| _(fill in — active AV engineer)_ | current AV industry | P1 | WhatsApp |
| _(fill in — robotics academic)_ | PhD / postdoc, published | P1 | email |
| _(fallback)_ | any roboticist willing to review + quote | P2 | any |

Contact at least 3 in parallel. Don't serialize.

## Ask (message template — EN)

> Hi [name], short ask. I'm in a hackathon this week (Cerebral Valley × Anthropic, "Built with Opus 4.7") shipping **Black Box** — a forensic copilot that reads a ROS bag and returns ranked root-cause hypotheses plus a scoped code patch. Two platforms: 5-camera autonomous car + NAO6 humanoid. Demo ships Apr 26.
>
> Would you have 10 minutes to look at one analysis output? If you find it credible, I'd love a 1–2 sentence quote I can use in the submission video. If you think it's off, tell me and I'll take the note. No obligation either way.
>
> Sample output: [PDF link or screenshot]
> Repo: [GitHub URL]

## Ask (message template — ES)

> Hola [nombre], una ask corta. Estoy en un hackathon esta semana (Cerebral Valley × Anthropic, "Built with Opus 4.7") shipeando **Black Box** — copilot forense que lee un ROS bag y devuelve hipótesis de causa raíz ranqueadas + un parche de código acotado. Dos plataformas: auto autónomo 5 cámaras + humanoid NAO6. Demo sale 26 abril.
>
> ¿Tenés 10 min para ver un análisis? Si lo ves creíble, me gustaría una frase de 1–2 oraciones para el video de la submission. Si ves algo flojo, decímelo y lo anoto. Sin obligación.
>
> Output ejemplo: [link PDF o screenshot]
> Repo: [URL GitHub]

## What to send them

- 1 PDF report (the bag-1 overexposure hero is the strongest — AE convergence failure, 4.5 s duration, clean patch)
- 1 screenshot of the unified diff
- Link to benchmark repo
- **Not** the raw bag. They won't open 55 GB. Our output should stand alone.

## Quote-quality guide

**Good quotes sound like:**
- *"The kind of analysis I'd expect from a senior robotics engineer, but in minutes."*
- *"Cross-view reasoning on five cameras is exactly what we don't have time to do manually."*
- *"I've never seen an LLM tool emit a patch I'd actually apply. This one I would."*
- *"This is the missing layer between 'bag collected' and 'bug filed.'"*

**Weak quotes we reject:**
- Generic *"cool project"* — not usable
- Over-hyped *"will change everything"* — not credible
- Technical inaccuracies — bad for us even if flattering

If the first draft is weak, ask once: *"Would you be willing to phrase it in terms of [specific capability]?"* Don't rewrite their words ourselves — put the revision in their mouth or drop it.

## Consent checklist

Before using the quote:

- [ ] Permission to attribute by name
- [ ] Permission to show affiliation (ex-NASA, etc.) — some contacts have NDA constraints
- [ ] Permission to use in demo video (public-facing)
- [ ] Permission to use in README / submission form
- [ ] Screenshot of the written consent kept in `data/session/testimonial_consent.txt` (not committed — PII)

## Fallback: no quote by Day 5

Ship without. Do **not** fabricate. Do **not** use an AI-generated endorsement. The grounding-gate principle applies to our own pitch: honesty > drama. Replace the punchline beat with *"Benchmark is open, two platforms, six days, you judge."*
