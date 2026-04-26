.PHONY: clean-frames demo-final demo-intro-outro

# Strip the (gitignored) Playwright PNG frame dirs that the UI capture
# scripts produce. Each run leaves ~600MB of intermediate frames behind.
clean-frames:
	rm -rf video_assets/final_ui_capture/_frames \
	       video_assets/ui_feature_inserts/_frames

# Re-render intro/outro cards with live cost from data/costs.jsonl.
demo-intro-outro:
	.venv/bin/python scripts/render_intro_outro.py

# Assemble the 3:00 visual-only demo from the existing block clips.
demo-final:
	bash scripts/build_final_demo.sh
