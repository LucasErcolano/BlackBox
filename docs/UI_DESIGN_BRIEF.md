# Black Box — UI Design Brief

> Forensic copilot for robots. When a robot crashes, a flight-data recorder tells you *what*. Black Box tells you *why* and hands you the patch.

**Repo:** https://github.com/LucasErcolano/BlackBox
**Stack:** FastAPI + HTMX + vanilla CSS (no React, no Tailwind, no build step). One stylesheet at `src/black_box/ui/static/style.css`. Two templates at `src/black_box/ui/templates/{index.html,progress.html}`. Server-rendered fragments swapped via HTMX.
**Hard constraint:** must keep working with HTMX-only swaps. No SPA rewrite. PRs that introduce a JS framework get rejected.

---

## 1. Vibe & emotional positioning

| Pole | Stay close to | Avoid |
|------|--------------|-------|
| Mood | NTSB accident report meets Bloomberg Terminal | Y-Combinator SaaS pastel |
| Authority | Editorial, sober, exhibits-and-evidence | Marketing, "wow factor" |
| Personality | Quiet expertise, no bravado, almost dry | Cute, playful, emoji, gradient |
| Speed signal | Calm steady cadence, telegraph clicks | Bouncy spring animations |
| Trust signal | Cited, timestamped, monospace receipts | Hand-wavy summaries |

Reference touchstones (in order of priority):
1. **NTSB final accident reports** — typography hierarchy, exhibits, table-driven evidence.
2. **Bloomberg Terminal / Reuters Eikon** — dense data without claustrophobia.
3. **Stripe documentation** — calm sans + monospace pairing.
4. **Linear app** — opinionated greys, restraint, microcopy.
5. **`werkzeug` / `traceback` debug pages** — engineering authenticity.

The product narrates a refutation: operator says "tunnel caused the crash" → Black Box says "no, RTK was already broken 43 min before the tunnel, here's the proof." UI must feel like a forensic exhibit, not a chat app.

---

## 2. Current palette (locked — extend, don't replace)

```css
:root {
  --serif: "IBM Plex Serif", Georgia, serif;
  --sans:  "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono:  ui-monospace, "SF Mono", Menlo, monospace;

  /* Light surface */
  --bg:       #f6f4ef;   /* warm paper */
  --surface:  #fffdf8;   /* exhibit card */
  --ink:      #1c1c1a;   /* near-black text */
  --muted:    #6b6b66;   /* secondary text */
  --line:     #d9d6cc;   /* hairline borders */
  --accent:   #b33;      /* refutation red, evidence-grade */

  /* Console (already in use for reasoning stream) */
  --console-bg:    #141412;
  --console-bg-2:  #1e1d1b;
  --console-line:  #2a2825;
  --console-text:  #e7e4db;
  --console-muted: #9a958a;
  --signal-amber:  #e0b14b;
  --signal-green:  #6fb26f;
}
```

**Don't introduce new hues without justification.** Black Box has earned its palette. Any new accent must show its work (refutation severity, ground-truth anchor, etc).

---

## 3. Typography spec

| Role | Family | Weight | Size | Letter-spacing | Notes |
|------|--------|--------|------|---------------|-------|
| H1 wordmark | Plex Serif | 600 | 2.25rem | -0.01em | Editorial masthead |
| H2 section | Plex Serif | 500 | 1.4rem | -0.005em | Roman numeral exhibits OK |
| Body | Plex Sans | 400 | 1.02rem | normal | line-height 1.55 |
| UI label | Plex Sans | 500 | 0.82rem | 0.06em UPPERCASE | Form fields, tab headers |
| Meta / caption | Plex Sans | 400 | 0.85rem | normal | `--muted` color |
| Console | SF Mono / ui-monospace | 400 | 0.88rem | normal | reasoning stream + evidence dumps |
| Citations | Plex Sans | 500 | 0.78rem | 0.04em | `[E1]` `[E2]` chips |

Pairing rule: serif headers tell you you're reading something authoritative; sans body keeps it utilitarian; mono is reserved for *receipts* (tool calls, telemetry, diffs, evidence IDs).

---

## 4. Surfaces to design

### 4.1 Landing / upload (`index.html`)
**Today:** centered 720px column, single form, IBM Plex masthead, file input + mode select + Analyze button.
**Polish asks:**
- Hero zone needs *one* sentence-of-proof (think NYT byline): "Refuted operator's tunnel hypothesis on the sanfer RTK case in 43 seconds. $0.46. Cited."
- Mode select needs to feel like a *choice with stakes*: Tier 1 forensic post-mortem vs Tier 2 scenario mining vs Tier 3 synthetic Q&A. Three radio cards with one-line contracts under each, not a dropdown.
- Drop zone for the file. Right now it's a default `<input type=file>`. Should accept drag-drop with a labeled target ("Drop ROS bag, MCAP, or zipped session"). Show file size + detected adapter inline.
- Tiny "Native Claude memory mounted" credibility card (already shipping per Lucas audit) needs typographic discipline — not an alert, more like a colophon footnote at the top right of the form card.

### 4.2 In-flight progress (`progress.html`)
**Today:** progress card with a 4px bar, stage label, percentage, and a dark "reasoning stream" console with pulsing dot + monospace lines fading in.
**Polish asks:**
- Stage names in plain English ("Decoding bag", "Sampling frames", "Running cross-camera analysis", "Grounding hypothesis", "Writing report"). Not just `analyzing` / `done`.
- Tool-call ledger underneath the reasoning stream — collapsed by default — showing each `tool_use` with input shape, output bytes, and cost-so-far. This is the killer feature for judges; right now it's invisible.
- Cost meter bound to running USD. Subtle. Right-aligned. Mono. Updates as events arrive.
- Steering input ("nudge the agent") — tiny single-line affordance below the stream. Send `POST /steer/{job_id}`. Already wired.

### 4.3 Evidence / report (no template yet)
**Today:** server returns a PDF link + diff URL after the run. There's no in-browser report view.
**Polish ask — the big one:**
Build an *exhibit-style* report page:
- Top: H1 hypothesis ("RTK heading subsystem failed at t=02:14:32, 43 min before tunnel entry").
- Verdict line in `--accent`: "**REFUTED** — operator hypothesis (tunnel) does not match telemetry."
- Three-column "exhibits" section. Each exhibit is a card with: Exhibit number (E1, E2…), title, single-line caption, embedded plot or frame thumbnail, evidence type chip (`telemetry` / `frame` / `source-diff` / `log-line`), and a "view source" link.
- Right rail: timeline scrubber. Hover an exhibit → highlights its window on the timeline. (HTMX `hx-trigger="mouseover"` is fine.)
- Bottom: scoped patch as a side-by-side diff viewer (already produced as HTML; just needs an in-app shell). NTSB-style "recommended corrective action" framing.

### 4.4 Memory card overlay (already shipping)
**Today:** 3-line block:
```
Native Claude memory mounted:
✓ bb-platform-priors        read_only
✓ bb-forensic-learnings-*   read_write
✓ promotion gated by verification ledger
```
**Polish asks:**
- Should look like a colophon, not an alert. Small caps label "MEMORY MOUNTS" above the rows. Mono check column. Mono store names. Mono mode column. All in `--muted` so it sits as context, not chrome.
- On hover, each row reveals a 1-sentence tooltip (e.g. "Read-only at the filesystem level — agent cannot mutate verified priors").

### 4.5 Run history / case index (doesn't exist yet)
**Optional but high-leverage:** a `/cases` page that lists all completed runs as a table — case key, mode, verdict (Confirmed / Refuted / Inconclusive), cost, duration, tags, link. Newspaper-archive feel. Pure HTMX.

---

## 5. Microcopy — change all of these

| Surface | Current | Replace with |
|---------|---------|--------------|
| Header sub | "A forensic copilot for robots." | (keep — works) |
| Intro paragraph | "Upload a ROS bag, MCAP, or zipped run directory. Black Box decodes the telemetry, replays the incident through a vision-capable model, and produces a signed post-mortem with timeline, hypotheses, and evidence." | Tighten to ≤ 30 words. "Hand it a robot recording. Get a cited post-mortem, an evidence trail, and a scoped patch — within a session of Opus 4.7." |
| Submit button | "Analyze" | "Open the case" or "Run the post-mortem" |
| Stage label "analyzing" | n/a | "Reasoning across 5 cameras" / "Grounding hypothesis against telemetry" |
| Footer | "Opus 4.7 · Managed Agents · hackathon build" | "Built with Opus 4.7 · Managed Agents · evidence-graded" |
| Empty state when no runs | n/a | "No cases on the docket yet." |

---

## 6. Components to build

A short list, in priority order:

1. **EvidenceCard** — exhibit-style card for the report page. Fields: number, title, caption, media slot, type chip, source link.
2. **VerdictBanner** — top-of-report banner. Three states: **CONFIRMED** (`--ink`), **REFUTED** (`--accent`), **INCONCLUSIVE** (`--muted`). Uppercase, letter-spaced.
3. **TimelineRail** — horizontal SVG track. Bag duration mapped to width. Highlights painted from suspicious-window data already produced by `analysis/windows.py`.
4. **ToolCallLedger** — collapsible monospace table. Columns: t-offset, tool, input-bytes, output-bytes, USD. Right-aligned numeric.
5. **CostMeter** — single mono number top-right. Updates on each event. Format `$0.0046` (4 decimals to communicate "we count fractional pennies"). Tooltip breaks down cached vs uncached tokens.
6. **DropZone** — drag-and-drop file target. States: idle, dragover, uploading, error. No icons; text-only.
7. **MemoryColophon** — the credibility card from §4.4.
8. **MicrocopyChip** — small `[E1]` style citation chip used inline in prose.

---

## 7. Pages and routes that exist or will

| Route | Method | Purpose | Status |
|-------|--------|---------|--------|
| `/` | GET | Landing + upload | exists, needs polish |
| `/analyze` | POST | Submit job | exists |
| `/jobs/{id}` | GET | Progress page | exists |
| `/jobs/{id}/events` | GET | HTMX SSE stream | exists |
| `/report/{id}` | GET | Exhibit-style report | **doesn't exist — design this** |
| `/diff/{id}` | GET | Side-by-side diff viewer | exists, plain |
| `/trace/{id}` | GET | Replayable evidence trace | exists, JSON-only |
| `/cases` | GET | Case archive | **doesn't exist — design this** |
| `/memory/native_status` | GET | Returns memory mount state | exists, JSON |

---

## 8. Animation budget

Restrained. The product is a forensic exhibit, not a game.

- 200ms fade-in on stream lines (already shipping).
- 400ms ease on progress bar fill (already shipping).
- 1.2s pulse on the "live" dot (already shipping).
- No bouncy springs. No parallax. No reveal-on-scroll.
- Loading state: `▌` blinking cursor (mono). Not a spinner, not skeleton boxes.

---

## 9. Sound (don't, but documenting)

No audio. Chime-on-completion would feel cheap. The pulse → green dot transition is the completion signal.

---

## 10. Accessibility

- Already in code: `aria-live="polite"` on the result region. Keep.
- `prefers-reduced-motion`: disable the pulse and fade-in animations.
- Colour: `--accent` (#b33) on `--bg` (#f6f4ef) clears AA at 16px+.
- Keyboard: every action reachable. The submit button is already focusable; the file input drag-drop must keep keyboard fallback.
- Screen reader: every exhibit needs `<figcaption>` — not a pseudo-element.

---

## 11. Don't-do list

- No emoji anywhere in product UI. Footer and microcopy too.
- No gradients on surfaces. Borders only.
- No icons that aren't text. (Icons that are text — `▌` `✓` `→` — are fine.)
- No marketing-scale headers ("Robotics, reimagined!"). The product reports facts.
- No dark mode toggle in v1. The light surface is *the brand*. Console regions are already dark; that's the contrast story.
- No social proof block, no logos wall, no testimonials block. This is a tool, not a pitch deck.

---

## 12. Source files to read before designing

In the repo, please skim:

1. `src/black_box/ui/static/style.css` — full current stylesheet (213 lines).
2. `src/black_box/ui/templates/index.html` — landing.
3. `src/black_box/ui/templates/progress.html` — in-flight.
4. `src/black_box/ui/app.py` — FastAPI handlers.
5. `demo_assets/streaming/replay_sanfer_tunnel.mp4` — current demo walkthrough.
6. `demo_assets/pdfs/sanfer_tunnel.pdf` — what the report PDF currently looks like (the in-app version should rhyme with this).
7. `docs/MANAGED_AGENTS_MEMORY.md` — explains the memory layers the colophon refers to.
8. `docs/PITCH.md`, `docs/DEMO_SCRIPT.md` — narrative voice and tone.

Repo: https://github.com/LucasErcolano/BlackBox

---

## 13. Deliverables you should produce

If you're Claude Design (or any pair-design partner) acting on this brief, please return:

1. **Updated `style.css`** — additions only, no rewrites of existing tokens.
2. **New template:** `src/black_box/ui/templates/report.html` — exhibit-style report page consuming a `Report` pydantic model (pass an example, I'll wire it).
3. **New template:** `src/black_box/ui/templates/cases.html` — case archive table.
4. **Polished `index.html`** — drop zone, three radio cards, refreshed microcopy, memory colophon.
5. **Polished `progress.html`** — stage names in English, tool-call ledger, cost meter, steering input.
6. **One screenshot** of each polished surface as a PNG so I can paste into the Devpost submission.
7. **Optional:** a Figma frame or a static HTML mock for the `/report/{id}` page.

Hard rules for the deliverable:
- Pure HTMX + CSS. No JS framework.
- Don't change any FastAPI route signatures — the templates need to consume what the server already returns.
- Don't introduce a build step. No PostCSS, no Sass, no Tailwind config.
- Reuse the existing `:root` token block; extend it only when justified.

---

## 14. One-paragraph elevator for the design partner

Black Box ingests a robot's flight-data recording (ROS bag / MCAP / zipped session), decodes the telemetry, samples frames anchored to suspicious telemetry windows, runs the whole thing through Claude Opus 4.7 with native Managed Agents memory stores attached, and produces an NTSB-style post-mortem with cited exhibits and a scoped patch. The current UI is a plain FastAPI + HTMX surface that works but reads like a developer's first-draft. We need it to feel like the front page of a forensic publication — quietly authoritative, monospaced where it counts, no chrome, no marketing. Light surface, near-black ink, refutation red, IBM Plex Serif + Sans + mono. The unique design move: the product literally narrates a *refutation* of an operator's hypothesis, so the verdict banner and exhibit-style layout are load-bearing, not decorative. Build that page.

---

*Brief authored 2026-04-25 for the Anthropic Build Hackathon (deadline 2026-04-26 20:00 EST). Feel free to push back on any of this — but push back with sketches, not opinions.*
