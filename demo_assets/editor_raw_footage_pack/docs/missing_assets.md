# Missing real assets

- **Real boat camera footage** — `data/final_runs/boat_lidar/bundle/` has lidar + summary only, no `.jpg`/`.mp4`. Substituted with `15_boat_report_broll.mp4` (real `report.md`). Not a fabricated robot view.
- **Real `vision_ab` side-by-side** — no shipped 4.6-vs-4.7 vision pair PNG. Used `visual_mining_v2_grid.png` + `d1_vision_plot.png` (real shipped vision charts) as the closest available proxy. Editor may want to recreate a tighter A/B card by hand.
- **Audio** — no clips include audio. Editor to add v/o + score.
- **Live websocket trace** — `/trace/{job_id}` rendered, but no real-time event flood; demo replay drives a fast pipeline. If editor wants more visible motion, re-record `02_live_analysis_ui.mp4` with longer dwell.
