#!/usr/bin/env python3
"""
Tests for JSONL parsing and session loading helpers in rlm_bridge.py.
"""

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import (
    build_context_payload,
    find_sessions_dir,
    load_sessions,
    load_workspace_sync,
    parse_jsonl_session,
    parse_jsonl_session_content,
)


class TestParseJsonlSession:
    def test_parse_jsonl_session_content_extracts_user_and_assistant(self):
        raw = "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "Hello"}],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "Hi there"}],
                        }
                    }
                ),
            ]
        )

        parsed = parse_jsonl_session_content(raw)

        assert "[user]: Hello" in parsed
        assert "[assistant]: Hi there" in parsed

    def test_parse_jsonl_session_ignores_non_user_assistant_roles(self):
        raw = "\n".join(
            [
                json.dumps(
                    {
                        "message": {
                            "role": "toolResult",
                            "content": [{"type": "text", "text": "tool output"}],
                        }
                    }
                ),
                json.dumps(
                    {
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "final"}],
                        }
                    }
                ),
            ]
        )

        parsed = parse_jsonl_session_content(raw)

        assert "tool output" not in parsed
        assert "[assistant]: final" in parsed

    def test_parse_jsonl_session_file_wrapper(self, tmp_path):
        session_file = tmp_path / "session_001.jsonl"
        payload = {
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "This is a test message"}],
            }
        }
        session_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")

        parsed = parse_jsonl_session(session_file)

        assert "[user]: This is a test message" in parsed

    def test_parse_jsonl_includes_compaction_and_branch_summary(self):
        raw = "\n".join(
            [
                json.dumps(
                    {
                        "type": "compaction",
                        "summary": "Resumen de memoria compactada",
                    }
                ),
                json.dumps(
                    {
                        "type": "branch_summary",
                        "content": {"text": "Resumen de rama activa"},
                    }
                ),
            ]
        )

        parsed = parse_jsonl_session_content(raw)

        assert "[memory-summary]: Resumen de memoria compactada" in parsed
        assert "[memory-summary]: Resumen de rama activa" in parsed


class TestLoadSessions:
    def test_load_sessions_nonexistent_directory(self, tmp_path):
        result = load_sessions(str(tmp_path / "does_not_exist"))
        assert "No sessions available" in result

    def test_load_sessions_finds_jsonl_files(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Ensure content length clears min-length filter in loader.
        long_text = "x" * 120
        payload = {
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": long_text}],
            }
        }
        (sessions_dir / "session_abc123.jsonl").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

        result = load_sessions(str(sessions_dir), max_sessions=5, max_chars=10_000)

        assert "SESSION:session_abc123" in result
        assert long_text in result

    def test_load_sessions_respects_max_sessions(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        for i in range(5):
            payload = {
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": f"session-{i}-" + "z" * 80}],
                }
            }
            file_path = sessions_dir / f"session_{i:03d}.jsonl"
            file_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

        result = load_sessions(str(sessions_dir), max_sessions=2, max_chars=10_000)

        assert result.count("SESSION:") == 2

    def test_load_sessions_ignores_sessions_index_file(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        (sessions_dir / "sessions.json").write_text('{"sessions": []}', encoding="utf-8")

        payload = {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "y" * 80}],
            }
        }
        (sessions_dir / "real_session.jsonl").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

        result = load_sessions(str(sessions_dir), max_sessions=5, max_chars=10_000)

        assert "SESSION:real_session" in result
        assert "SESSION:sessions" not in result

    def test_load_sessions_uses_sessions_index_metadata(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        (sessions_dir / "sessions.json").write_text(
            json.dumps(
                {
                    "sessions": [
                        {
                            "id": "session_meta",
                            "title": "Plan semanal",
                            "branchId": "branch-a",
                            "parentId": "root-1",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        payload = {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "z" * 120}],
            }
        }
        (sessions_dir / "session_meta.jsonl").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

        result = load_sessions(str(sessions_dir), max_sessions=5, max_chars=10_000)

        assert "TITLE:Plan semanal" in result
        assert "BRANCH:branch-a" in result
        assert "PARENT:root-1" in result

    def test_load_sessions_uses_map_style_sessions_index_metadata(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        (sessions_dir / "sessions.json").write_text(
            json.dumps(
                {
                    "sessionKeyA": {
                        "sessionId": "session_map",
                        "title": "Mapa oficial",
                        "branchId": "branch-map",
                        "parentId": "parent-map",
                    }
                }
            ),
            encoding="utf-8",
        )

        payload = {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "m" * 120}],
            }
        }
        (sessions_dir / "session_map.jsonl").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

        result = load_sessions(str(sessions_dir), max_sessions=5, max_chars=10_000)

        assert "TITLE:Mapa oficial" in result
        assert "BRANCH:branch-map" in result
        assert "PARENT:parent-map" in result

    def test_load_sessions_handles_overflow_timestamp_from_index(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        (sessions_dir / "sessions.json").write_text(
            json.dumps(
                {
                    "sessions": [
                        {
                            "id": "session_overflow",
                            "updatedAt": "1e20",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        payload = {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "o" * 120}],
            }
        }
        (sessions_dir / "session_overflow.jsonl").write_text(
            json.dumps(payload) + "\n",
            encoding="utf-8",
        )

        result = load_sessions(str(sessions_dir), max_sessions=5, max_chars=10_000)
        assert "DATE:unknown-date" in result


class TestWorkspaceAndAgentResolution:
    def test_load_workspace_accepts_lowercase_memory(self, tmp_path):
        (tmp_path / "memory.md").write_text("lower memory", encoding="utf-8")
        result = load_workspace_sync(str(tmp_path))
        assert "=== MEMORY.md ===" in result
        assert "lower memory" in result

    def test_find_sessions_dir_prefers_explicit_agent_id(self, tmp_path):
        agents_dir = tmp_path / "agents"
        (agents_dir / "active-a" / "sessions").mkdir(parents=True)
        (agents_dir / "active-a" / "sessions" / "s1.jsonl").write_text("{}", encoding="utf-8")
        (agents_dir / "other-b" / "sessions").mkdir(parents=True)
        (agents_dir / "other-b" / "sessions" / "s2.jsonl").write_text("{}", encoding="utf-8")

        resolved = find_sessions_dir(str(tmp_path), agent_id="active-a")
        assert resolved.endswith("active-a/sessions")


class TestContextChunking:
    def test_chunks_mode_skips_sentinel_no_sessions_marker(self):
        payload, fmt = build_context_payload(
            workspace_content="workspace",
            sessions_content="[No sessions available]",
            context_format="chunks",
            pi_profile_name="off",
        )
        assert fmt == "chunks"
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0].startswith("=== WORKSPACE ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
