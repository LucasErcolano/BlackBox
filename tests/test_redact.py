"""#79 — redactor smoke tests over planted secrets + paths."""
from __future__ import annotations

from black_box.security import redact_text


def test_anthropic_key_redacted():
    src = "key = sk-ant-api03-AAAAaaaaBBBBbbbbCCCCccccDDDDddddEEEEeeeeFFFFffffGGGGgggg"
    out, stats = redact_text(src)
    assert "sk-ant-" not in out
    assert "[REDACTED:anthropic_key]" in out
    assert stats.counts.get("anthropic_key") == 1


def test_aws_key_redacted():
    out, stats = redact_text("export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
    assert "AKIA" not in out
    assert stats.counts.get("aws_access_key") == 1


def test_github_pat_redacted():
    out, _ = redact_text("token = ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef0123")
    assert "ghp_" not in out


def test_email_redacted():
    out, stats = redact_text("contact ops@example.com for triage")
    assert "ops@example.com" not in out
    assert stats.counts.get("email") == 1


def test_ipv4_redacted():
    out, stats = redact_text("rosbridge ws://10.0.0.42:9090")
    assert "10.0.0.42" not in out
    assert stats.counts.get("ipv4") == 1


def test_unix_home_path_stripped():
    out, _ = redact_text("loaded /home/lucas/Desktop/bags/sanfer/2_sensors.bag from disk")
    assert "lucas" not in out
    assert "/home/<user>" in out
    assert "/Desktop/bags/sanfer/2_sensors.bag" in out  # tail kept


def test_planted_synthetic_secret_and_path_in_bag_index():
    """The smoke case from the issue — a redactor pass over a bag-index blob."""
    blob = (
        "frame index for /home/lucas/data/sanfer/2_cam-lidar.bag\n"
        "operator email: lucas@example.com\n"
        "deploy token: ghp_abcdefghijklmnopqrstuvwxyzABCDEFGH12\n"
        "uplink: 192.168.1.50:8000\n"
    )
    out, stats = redact_text(blob)
    assert "lucas" not in out
    assert "ghp_" not in out
    assert "192.168.1.50" not in out
    assert stats.total() >= 4


def test_allowlisted_hostnames_kept():
    out, _ = redact_text("docs at https://docs.claude.com/en/api and repo at github.com/foo/bar")
    assert "docs.claude.com" in out
    assert "github.com" in out


def test_random_hostname_redacted():
    out, stats = redact_text("calling internal.acme-corp.example for telemetry")
    assert "acme-corp.example" not in out
    assert stats.counts.get("hostname", 0) >= 1


def test_managed_agent_default_network_is_none():
    """#79 — default sandbox policy must be 'none' so opt-in egress is explicit."""
    from black_box.analysis.managed_agent import ForensicAgentConfig
    cfg = ForensicAgentConfig()
    assert cfg.network == "none"
