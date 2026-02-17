#!/usr/bin/env python3
"""
Tests for JSONL parsing and session loading helpers in rlm_bridge.py.
"""

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import load_sessions, parse_jsonl_session, parse_jsonl_session_content


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
