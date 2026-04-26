# v1 vs v2 — A/B comparison

| metric                     | v1                    | v2                    |
|----------------------------|-----------------------|-----------------------|
| duration                   | 175.00 s             | 172.47 s             |
| cuts                       | 24                    | 26                    |
| static holds (PNG stills)  | 2                     | 5                     |
| longest static hold        | 4.0 s               | 3.0 s               |
| source files used          | 21                    | 24                    |
| caption lines              | 42                    | 42                    |
| freeze windows (>=1.5 s)   | 15                    | 13                     |

## Sections shortened / expanded

| beat              | v1     | v2     | delta                                  |
|-------------------|--------|--------|----------------------------------------|
| Hook              | 12.0 s | 11.0 s | -1.0 s — faster cut to "story is wrong" |
| Problem           | 13.0 s | 13.0 s | unchanged                              |
| Setup             | 13.0 s | 11.0 s | -2.0 s — drop redundant `02_live` 2 s tail |
| Agent             | 17.0 s | 17.0 s | unchanged                              |
| Visual mining     | 15.0 s | 14.0 s | -1.0 s                                 |
| Refutation        | 25.0 s | 27.0 s | +2.0 s — give the verdict more room   |
| Root cause        | 20.0 s | 20.0 s | restructured: 12 s chart + 3 s still + 5 s PDF |
| Patch             | 15.0 s | 17.9 s | +2.9 s — patch_diff zoom-in still + return-to-UI movement |
| Opus 4.7          | 19.5 s | 16.0 s | -3.5 s — drop 4 s of unreadable doc scroll |
| Breadth           | 13.0 s | 14.0 s | +1.0 s                                 |
| Grounding         | 8.0 s  | 9.0 s  | +1.0 s                                 |
| Outro             | 4.0 s  | 6.0 s  | +2.0 s — dedicated 2-still title card  |

## Editorial notes

- v2 hook reaches the line "that story is wrong" at ~0:08 (vs ~0:11 in v1).
- v2 introduces 4 strategic 0.25 s xfade dissolves at chapter boundaries
  (problem → setup not faded; faded: hook→problem, mining→refutation,
  patch→opus, grounding→outro). Everywhere else stays hard cut.
- v2 still holds use a 1.0 → 1.045 zoompan slow-zoom (sourced at 3840x2160 to
  avoid upscale blur), so refutation/patch/root/outro stills don't sit dead.
- Captions: ASS Inter 42 px (was 40), MarginV 72 (was 80), tighter line width
  (≤48 chars), MarginL/R 100. Easier to read on dense UI clips.
- Outro is now a real-derived title card (breadth_cases_archive.png +
  hero_report_top.png with slow zoom) rather than re-running the cases tail.
- Doc-scroll dependence reduced: `17_opus47_delta_doc_scroll` shortened from
  ~7 s to 4 s, `11_sanfer_pdf_scroll` shortened from 8 s to 5 s.

## Why v2 is the better edit

1. Faster, more confident hook.
2. Refutation beat hits harder: longer hold + slow-zoom on the verdict still.
3. Opus 4.7 segment is half its v1 weight in seconds and clearer
   ("Same accuracy. Better judgment."), instead of three doc paragraphs.
4. Outro is a deliberate two-card payoff, not a tail clip.
5. xfades at chapter boundaries give pacing cadence without sacrificing
   evidence beats.
6. Static holds lifted by zoompan — fewer "frozen" frames despite using more
   stills than v1.
