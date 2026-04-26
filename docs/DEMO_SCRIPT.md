
## Nuevo demo script — 3:00

|      Time | Beat                   | Screen                                                             | Voice-over                                                                                                                                                                                                                                                              |
| --------: | ---------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0:00–0:12 | Hook                   | Lucas / auto real / recording                                      | “The operator told me the GPS failed under a tunnel. Black Box checked the recording and said: that story is wrong.”                                                                                                                                                    |
| 0:12–0:25 | Product problem        | Nueva intake UI, drag/drop, mode cards                             | “Robotics teams collect hours of video, lidar, telemetry and controller logs. The evidence exists, but the forensic work is still manual.”                                                                                                                              |
| 0:25–0:38 | Setup                  | Upload `.bag`, mode card, job starts                               | “I give Black Box one real driving session. No labels. No handcrafted rubric. Just the operator’s note: check the tunnel.”                                                                                                                                              |
| 0:38–0:55 | Live product surface   | Live job panel, stages, right rail memory mounts                   | “This is not a one-shot summary. Opus 4.7 runs as a managed forensic agent: reading files, using tools, streaming events, and checking memory from previous runs.”                                                                                                      |
| 0:55–1:08 | Visual mining          | 5-camera grid / exhibit media / telemetry-selected window          | “It does not send every frame. Telemetry selects suspicious windows, then high-resolution visual mining checks the relevant camera views.”                                                                                                                              |
| 1:08–1:35 | Refutation             | Verdict banner: “It wasn’t the tunnel”; operator quote vs evidence | “Here is the key moment. The tunnel did mildly degrade GNSS: fewer satellites, wider accuracy. But the RTK heading failure was already present 43 minutes earlier, and drive-by-wire was never engaged. The tunnel could not have caused the reported behavior change.” |
| 1:35–1:55 | Root cause             | Plots: moving-base healthy, rover invalid, REL_POS_VALID flat      | “The real failure is lower level. The moving-base antenna is healthy, but the rover never gets valid RTK heading. The correction path was broken before the car left the lot.”                                                                                          |
| 1:55–2:12 | Money shot             | Report page, 22-line diff, approve/reject, append ledger           | “And the output is not just a report. It gives a scoped patch: RTCM message IDs, a UART link check, and a human-review gate. Black Box proposes the diff; the engineer approves it.”                                                                                    |
| 2:12–2:34 | Opus 4.7 delta         | One panel: “Same accuracy. Better judgment. More eyes.”            | “This is why Black Box is built on Opus 4.7. Not because simple cases need a bigger model — 4.6 and 4.7 tie there. But robot forensics punishes confident wrong answers. In our benchmark, 4.6 committed on every under-specified case. 4.7 abstained every time.”      |
| 2:34–2:45 | Vision + speed proof   | Fine-grain image token: 4.6 0/3, 4.7 3/3; latency badge            | “It also sees fine visual details that 4.6 loses under downsampling, and runs about thirty percent faster on telemetry and text runs.”                                                                                                                                  |
| 2:45–2:53 | Generalization montage | `/cases`: boat lidar, other car runs, clean case, injected bugs    | “And this is not a single-car demo. The same archive includes more car sessions, a robotic boat lidar case, clean recordings, and injected benchmark failures.”                                                                                                         |
| 2:53–3:00 | Grounding + close      | Clean case: empty / insufficient evidence; repo + cost             | “When there is no evidence, it makes no claim. Open benchmark. Reproducible runs. Robot forensics in minutes, for cents.”                                                                                                                                               |

## Continuous VO version

```text
The operator told me the GPS failed under a tunnel.
Black Box checked the recording and said: that story is wrong.

Robotics teams collect hours of video, lidar, telemetry and controller logs.
The evidence exists, but the forensic work is still manual.

I give Black Box one real driving session.
No labels. No handcrafted rubric.
Just the operator’s note: check the tunnel.

This is not a one-shot summary.
Opus 4.7 runs as a managed forensic agent: reading files, using tools, streaming events, and checking memory from previous runs.

It does not send every frame.
Telemetry selects suspicious windows, then high-resolution visual mining checks the relevant camera views.

Here is the key moment.
The tunnel did mildly degrade GNSS: fewer satellites, wider accuracy.
But the RTK heading failure was already present 43 minutes earlier, and drive-by-wire was never engaged.
The tunnel could not have caused the reported behavior change.

The real failure is lower level.
The moving-base antenna is healthy, but the rover never gets valid RTK heading.
The correction path was broken before the car left the lot.

And the output is not just a report.
It gives a scoped patch: RTCM message IDs, a UART link check, and a human-review gate.
Black Box proposes the diff; the engineer approves it.

This is why Black Box is built on Opus 4.7.
Not because simple cases need a bigger model — 4.6 and 4.7 tie there.
But robot forensics punishes confident wrong answers.
In our benchmark, 4.6 committed on every under-specified case.
4.7 abstained every time.

It also sees fine visual details that 4.6 loses under downsampling,
and runs about thirty percent faster on telemetry and text runs.

And this is not a single-car demo.
The same archive includes more car sessions, a robotic boat lidar case, clean recordings, and injected benchmark failures.

When there is no evidence, it makes no claim.
Open benchmark.
Reproducible runs.
Robot forensics in minutes, for cents.
```

## Panel visual para Opus 4.7

Usaría exactamente esto, grande y simple:

```text
Same accuracy. Better judgment. More eyes.

Simple post-mortems
4.6: 67%     4.7: 67%

Under-specified cases
4.6: 0% abstention     4.7: 100% abstention

Wrong operator hypothesis
4.6 Brier: 0.239     4.7 Brier: 0.162

Fine-grain vision
4.6: 0/3     4.7: 3/3

Telemetry/text latency
4.7: ~30% faster
```

Ese panel se sostiene muy bien porque Anthropic también posiciona Opus 4.7 como mejor en tareas largas, razonamiento sostenido, vision y verificación de outputs, y mantiene el mismo pricing que Opus 4.6. ([Anthropic][2]) Además, la documentación de Managed Agents calza con tu loop: agente, environment, session, events, tools, streaming, steering y estado persistente. ([Claude Platform][3])

## Cómo aprovechar la nueva UI

Con la UI nueva, el video no debería parecer “screen recording de terminal”. Mostrá:

* **Intake** al principio: mode cards + drop zone.
* **Live job panel** durante análisis: polling, stages, memory mounts, pipeline glyph.
* **Report** para el payoff: verdict banner, exhibits, chips, trace rows, diff.
* **Cases archive** para generalización: 8 filas, counts, bote + autos + clean/injected.
* **Recco buttons** al cierre: Download report, Copy Linear ticket, Append ledger.

El repo ya declara FastAPI + HTMX UI con upload → progress → diff, Managed Agents, grounding gate, memory, HITL approve/reject, steering, rollback, trace y visual mining shipped. ([GitHub][4]) La sección `visual_mining_v2` también respalda la parte de 5 cámaras en un prompt, thumbnails 800×600, escalamiento a 3.75MP y ventanas ancladas en telemetry. ([GitHub][4])

## Corte si se pasa de 3 minutos

Primero recortaría **generalización** de 8s a 4s.
Después recortaría **visual mining** de 13s a 8s.
No recortaría:

* la refutación del túnel,
* el root cause,
* el diff,
* el panel Opus 4.7.

El orden de prioridad final es:

1. **It wasn’t the tunnel.**
2. **Here is the actual RTK failure.**
3. **Here is the scoped patch.**
4. **4.7 abstains where 4.6 commits wrong.**
5. **The UI makes this feel like a product.**

