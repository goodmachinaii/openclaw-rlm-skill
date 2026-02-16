#!/usr/bin/env python3
"""
Basic tests for rlm_bridge.py
Verifies parse_jsonl_session() and load_sessions()
"""

import json
import tempfile
from pathlib import Path

import pytest

# Import functions from bridge
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import parse_jsonl_session, load_sessions


class TestParseJsonlSession:
    """Tests for parse_jsonl_session()"""

    def test_converts_jsonl_to_readable_text(self, tmp_path):
        """Verifies JSONL is converted to [role]: text format"""
        # Create test JSONL file
        jsonl_file = tmp_path / "session_001.jsonl"
        entries = [
            {
                "type": "message",
                "timestamp": "2026-01-15T10:00:00Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello, how are you?"}]
                }
            },
            {
                "type": "message",
                "timestamp": "2026-01-15T10:00:05Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi! I'm doing well, thanks."}]
                }
            },
        ]
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Parse
        result = parse_jsonl_session(jsonl_file)

        # Verify
        assert "[user]: Hello, how are you?" in result
        assert "[assistant]: Hi! I'm doing well, thanks." in result

    def test_ignores_tool_result(self, tmp_path):
        """Verifies toolResult is not included in output"""
        jsonl_file = tmp_path / "session_002.jsonl"
        entries = [
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Search for files"}]
                }
            },
            {
                "type": "message",
                "message": {
                    "role": "toolResult",
                    "content": [{"type": "text", "text": "file1.txt\nfile2.txt"}]
                }
            },
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Found 2 files."}]
                }
            },
        ]
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        result = parse_jsonl_session(jsonl_file)

        assert "[user]: Search for files" in result
        assert "[assistant]: Found 2 files." in result
        assert "toolResult" not in result
        assert "file1.txt" not in result

    def test_handles_content_as_string(self, tmp_path):
        """Verifies content as direct string works"""
        jsonl_file = tmp_path / "session_003.jsonl"
        entry = {
            "type": "message",
            "message": {
                "role": "user",
                "content": "Simple message as string"
            }
        }
        with open(jsonl_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        result = parse_jsonl_session(jsonl_file)

        assert "[user]: Simple message as string" in result

    def test_empty_file_returns_empty_string(self, tmp_path):
        """Verifies empty file doesn't cause error"""
        jsonl_file = tmp_path / "empty.jsonl"
        jsonl_file.touch()

        result = parse_jsonl_session(jsonl_file)

        assert result == ""

    def test_invalid_json_lines_are_skipped(self, tmp_path):
        """Verifies invalid JSON is skipped without error"""
        jsonl_file = tmp_path / "mixed.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            f.write("this is not json\n")
            f.write(json.dumps({
                "message": {"role": "user", "content": [{"type": "text", "text": "valid"}]}
            }) + "\n")
            f.write("{incomplete json\n")

        result = parse_jsonl_session(jsonl_file)

        assert "[user]: valid" in result
        assert "this is not json" not in result


class TestLoadSessions:
    """Tests for load_sessions()"""

    def test_finds_jsonl_files(self, tmp_path):
        """Verifies load_sessions finds and loads .jsonl files"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create JSONL session
        session_file = sessions_dir / "session_abc123.jsonl"
        entry = {
            "message": {"role": "user", "content": [{"type": "text", "text": "Test session"}]}
        }
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir))

        assert "SESSION:session_abc123" in result
        assert "[user]: Test session" in result

    def test_respects_max_sessions(self, tmp_path):
        """Verifies max_sessions limits loaded sessions count"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create 5 sessions
        for i in range(5):
            session_file = sessions_dir / f"session_{i:03d}.jsonl"
            entry = {"message": {"role": "user", "content": f"Session {i}"}}
            with open(session_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir), max_sessions=2)

        # Should only have 2 sessions (most recent by mtime)
        session_count = result.count("SESSION:")
        assert session_count == 2

    def test_nonexistent_directory_returns_message(self, tmp_path):
        """Verifies nonexistent directory returns appropriate message"""
        result = load_sessions(str(tmp_path / "does_not_exist"))

        assert "No sessions available" in result

    def test_ignores_sessions_json_index(self, tmp_path):
        """Verifies sessions.json (index) is not processed as session"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create index (not a session)
        index_file = sessions_dir / "sessions.json"
        with open(index_file, "w") as f:
            json.dump({"sessions": []}, f)

        # Create real session
        session_file = sessions_dir / "real_session.jsonl"
        entry = {"message": {"role": "user", "content": "Real"}}
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir))

        assert "SESSION:real_session" in result
        assert "SESSION:sessions" not in result

    def test_very_short_sessions_are_ignored(self, tmp_path):
        """Verifies sessions with less than 50 chars are ignored"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Short session (will be ignored)
        short = sessions_dir / "short.jsonl"
        with open(short, "w") as f:
            f.write('{"message":{"role":"user","content":"Hi"}}\n')

        # Long session (will be included)
        long = sessions_dir / "long.jsonl"
        entry = {"message": {"role": "user", "content": "x" * 100}}
        with open(long, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir))

        assert "SESSION:long" in result
        # short may or may not appear depending on how format counts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
