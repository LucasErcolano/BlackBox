# SECURITY — privacy posture, retention, access

This document is normative. Anything not listed here is not promised.

## Sandbox network policy

- Default: **`network="none"`** in `ForensicAgentConfig` (per #79). The Managed Agents sandbox runs without egress.
- Steps that need outbound network (e.g. fetching a public benchmark dataset) must opt in explicitly. Each opt-in is logged with a one-line reason in the session record. There is no "allow once, forget" mode.
- Inbound egress is never allowed. Reports + diffs are written to local disk; the operator pulls them out manually.

## What is uploaded, where

| Artifact | Destination | Purpose | Retention |
|---|---|---|---|
| Bag (`.bag`, `.mcap`, etc.) | Mounted into the Managed Agents sandbox under `/mnt/session/uploads/` | Forensic analysis | Lifetime of the agent session; deleted when the session ends |
| Frames extracted by ingestion | Sandbox local FS only | Vision pass on suspicious windows | Lifetime of the agent session |
| Source-tree snapshot (controllers) | Sandbox local FS only | Patch suggestion grounding | Lifetime of the agent session |
| Telemetry windows + cost ledger | `data/costs.jsonl` (local repo) | Cost + token telemetry, audit | Until the operator deletes the file |
| Final report PDF + diff | `data/reports/<job_id>/` (local repo) | Operator-facing artifact | Until the operator deletes the file |
| Verification notes | `data/reports/<job_id>/verification_note.md` + `data/memory/verification.jsonl` | Append-only human ledger (#86) | Until the operator deletes the file |

Anthropic API: prompts and responses transit the Anthropic API per [Anthropic's data-handling policy](https://docs.claude.com/en/docs/data-and-privacy). No content is uploaded to any other third-party.

## Redaction

Run automatically at the upload boundary and again at the report-render boundary by `black_box.security.redact_text`:

- API keys (Anthropic `sk-ant-`, OpenAI `sk-`, AWS `AKIA…`, GitHub PATs `ghp_*` / `github_pat_*`, generic `Bearer …`).
- Email addresses.
- IPv4 + IPv6.
- Non-allowlisted hostnames (`localhost` and a small list of project-relevant domains stay; everything else is redacted).
- Absolute home-directory paths (`/home/<user>/…`, `/Users/<user>/…`, `C:\Users\<user>\…`) — user prefix stripped, relative tail kept so the path is still useful in debugging.
- Generic high-entropy tokens (≥40 chars base64-ish) that don't look like a Git SHA.

False negatives are expected. **The redactor reduces blast radius; it does not promise leak-proofing.** Operators must still avoid pasting real secrets into bag files.

## Access model

- Reports + diffs + cost logs live on the operator's local disk. There is no hosted view.
- The hackathon demo UI binds to `127.0.0.1:8000` by default. Do not expose it publicly without an authenticating reverse proxy.
- The submission video may show partial findings; raw bags are not committed.

## Retention + purge

- **Per-session purge.** Deleting `data/reports/<job_id>/` removes the report, the verification notes, and any session-local frames.
- **Global purge** (suitable when a contributor changes laptops):
  ```bash
  rm -rf data/reports data/uploads data/jobs data/patches data/costs.jsonl data/memory/verification.jsonl
  ```
- Anthropic-side retention follows the [API data-handling policy](https://docs.claude.com/en/docs/data-and-privacy).

## Out of scope (tracked separately)

- Credentials isolation via MCP / vault — see #80.
- Prompt-injection role segregation verification — see #81.
- Visual PII redaction (faces, plates) — see #93.
