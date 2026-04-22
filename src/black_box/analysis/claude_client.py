"""Claude API client for Black Box analysis with prompt caching and cost tracking."""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from base64 import b64encode

from PIL import Image
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

from .grounding import ground_post_mortem, ground_scenario_mining
from .schemas import PostMortemReport, ScenarioMiningReport


load_dotenv()


@dataclass
class CostLog:
    """Tracks API usage and cost for a single analysis call."""
    cached_input_tokens: int
    uncached_input_tokens: int
    cache_creation_tokens: int
    output_tokens: int
    usd_cost: float
    wall_time_s: float
    model: str
    prompt_kind: str


class ClaudeClient:
    """Wraps anthropic.Anthropic() with caching, image handling, and cost tracking."""

    # Opus 4.7 pricing (can be overridden via OPUS_PRICING_JSON env var)
    DEFAULT_PRICING = {
        "input": 15.0,  # $ per MTok
        "cache_write": 18.75,  # $ per MTok
        "cache_read": 1.50,  # $ per MTok
        "output": 75.0,  # $ per MTok
    }

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-opus-4-7"
        self.pricing = self._load_pricing()
        self._ensure_costs_file()

    def _load_pricing(self) -> dict:
        """Load pricing from env var or use defaults."""
        pricing_json = os.getenv("OPUS_PRICING_JSON")
        if pricing_json:
            return json.loads(pricing_json)
        return self.DEFAULT_PRICING

    def _ensure_costs_file(self):
        """Ensure data/costs.jsonl exists."""
        repo_root = self._find_repo_root()
        costs_dir = repo_root / "data"
        costs_dir.mkdir(parents=True, exist_ok=True)
        self.costs_file = costs_dir / "costs.jsonl"

    def _find_repo_root(self) -> Path:
        """Walk up from __file__ until we find pyproject.toml."""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        raise RuntimeError("Could not find repo root (pyproject.toml)")

    def _resize_image(self, image: Image.Image, max_side: int) -> Image.Image:
        """Resize image to max_side, preserving aspect ratio."""
        w, h = image.size
        if max(w, h) <= max_side:
            return image
        scale = max_side / max(w, h)
        return image.resize(
            (int(w * scale), int(h * scale)), Image.Resampling.LANCZOS
        )

    def _image_to_base64_jpeg(
        self, image: Image.Image, quality: int = 85
    ) -> str:
        """Convert PIL Image to base64 JPEG string."""
        buf = image.tobytes()
        # For simplicity, use PIL's native JPEG encoding
        from io import BytesIO
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality)
        b64 = b64encode(output.getvalue()).decode("utf-8")
        return b64

    def _build_messages(
        self,
        prompt_spec: dict,
        user_fields: dict | None = None,
        images: list[Image.Image] | None = None,
        resolution: Literal["thumb", "hires"] = "thumb",
    ) -> tuple[list[dict], str]:
        """Build system + messages for API call. Returns (system_blocks, user_content_text)."""
        if user_fields is None:
            user_fields = {}

        # Render user template
        user_text = prompt_spec["user_template"].format(**user_fields)

        # Add image blocks if provided
        image_blocks = []
        if images:
            max_side = 800 if resolution == "thumb" else 1920
            for img in images:
                resized = self._resize_image(img, max_side)
                b64 = self._image_to_base64_jpeg(resized)
                image_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    }
                )

        # Construct system blocks with cache control
        system_blocks = [
            {
                "type": "text",
                "text": prompt_spec["system"],
                "cache_control": {"type": "ephemeral"},
            }
        ]
        system_blocks.extend(prompt_spec.get("cached_blocks", []))

        return system_blocks, user_text, image_blocks

    def analyze(
        self,
        prompt_spec: dict,
        images: list[Image.Image] | None = None,
        user_fields: dict | None = None,
        resolution: Literal["thumb", "hires"] = "thumb",
        max_tokens: int = 4000,
    ) -> tuple[BaseModel, CostLog]:
        """
        Run Claude analysis with aggressive caching.

        Args:
            prompt_spec: dict from prompts module (system, cached_blocks, user_template, schema)
            images: optional list of PIL Image objects
            user_fields: dict of placeholders for user_template
            resolution: "thumb" (800px) or "hires" (1920px)
            max_tokens: max output tokens

        Returns:
            (parsed_response: BaseModel, cost_log: CostLog)
        """
        if user_fields is None:
            user_fields = {}

        start_time = time.time()
        schema = prompt_spec["schema"]

        # Build messages
        system_blocks, user_text, image_blocks = self._build_messages(
            prompt_spec, user_fields, images, resolution
        )

        # Construct content with images
        content = image_blocks + [{"type": "text", "text": user_text}]

        # Add JSON instruction
        final_text = (
            content[-1]["text"]
            + "\n\nRespond with a single JSON object matching the schema. No preamble, no markdown."
        )
        content[-1]["text"] = final_text

        # First attempt
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": content}],
        )

        # Parse response
        text = response.content[0].text
        try:
            # Strip markdown fences defensively
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            result = schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Retry once
            retry_content = (
                content[:-1]
                + [
                    {
                        "type": "text",
                        "text": final_text
                        + f"\n\nPrevious attempt failed: {str(e)}. Please correct and retry.",
                    }
                ]
            )
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_blocks,
                messages=[{"role": "user", "content": retry_content}],
            )
            text = response.content[0].text
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            data = json.loads(text)
            result = schema.model_validate(data)

        # Calculate cost
        usage = response.usage
        wall_time = time.time() - start_time

        cached_input = getattr(usage, "cache_read_input_tokens", 0)
        uncached_input = usage.input_tokens
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
        output = usage.output_tokens

        # USD cost calculation
        input_cost = (
            uncached_input * self.pricing["input"]
            + cache_creation * self.pricing["cache_write"]
            + cached_input * self.pricing["cache_read"]
        ) / 1e6
        output_cost = output * self.pricing["output"] / 1e6
        total_cost = input_cost + output_cost

        cost_log = CostLog(
            cached_input_tokens=cached_input,
            uncached_input_tokens=uncached_input,
            cache_creation_tokens=cache_creation,
            output_tokens=output,
            usd_cost=total_cost,
            wall_time_s=wall_time,
            model=self.model,
            prompt_kind=prompt_spec.get("name", "unknown"),
        )

        # Append to costs.jsonl
        self._append_cost_log(cost_log)

        if isinstance(result, PostMortemReport):
            result = ground_post_mortem(result)
        elif isinstance(result, ScenarioMiningReport):
            result = ground_scenario_mining(result)

        return result, cost_log

    def _append_cost_log(self, log: CostLog):
        """Append CostLog as JSON line to costs.jsonl."""
        with open(self.costs_file, "a") as f:
            f.write(
                json.dumps(
                    {
                        "cached_input_tokens": log.cached_input_tokens,
                        "uncached_input_tokens": log.uncached_input_tokens,
                        "cache_creation_tokens": log.cache_creation_tokens,
                        "output_tokens": log.output_tokens,
                        "usd_cost": log.usd_cost,
                        "wall_time_s": log.wall_time_s,
                        "model": log.model,
                        "prompt_kind": log.prompt_kind,
                    }
                )
                + "\n"
            )

    def total_spent_usd(self) -> float:
        """Sum all costs from costs.jsonl."""
        if not self.costs_file.exists():
            return 0.0
        total = 0.0
        with open(self.costs_file, "r") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    total += entry.get("usd_cost", 0.0)
        return total
