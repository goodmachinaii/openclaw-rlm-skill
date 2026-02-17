#!/usr/bin/env python3
"""
Tests for retry/fallback behavior in rlm_bridge.py.
"""

import json
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import main, run_rlm


def _successful_result():
    usage = MagicMock()
    usage.to_dict.return_value = {
        "model_usage_summaries": {
            "kimi-k2.5": {
                "total_calls": 1,
                "total_input_tokens": 2000,
                "total_output_tokens": 1000,
            }
        }
    }
    return SimpleNamespace(response="OK", execution_time=0.5, usage_summary=usage)


class TestRunRlmRetries:
    @patch("rlm_bridge._create_rlm")
    def test_rate_limit_returns_friendly_message(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.side_effect = Exception("Error 429: rate limit exceeded")
        mock_create_rlm.return_value = mock_rlm

        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2.5",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        assert result["status"] == "rate_limited"

    @patch("rlm_bridge.time.sleep", return_value=None)
    @patch("rlm_bridge._create_rlm")
    def test_transient_timeout_retries_then_succeeds(self, mock_create_rlm, _mock_sleep):
        failing_rlm = MagicMock()
        failing_rlm.completion.side_effect = Exception("Connection timeout")

        working_rlm = MagicMock()
        working_rlm.completion.return_value = _successful_result()

        mock_create_rlm.side_effect = [failing_rlm, working_rlm]

        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2.5",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
            max_retries=1,
            retry_backoff_seconds=0.01,
        )

        assert result["status"] == "ok"
        assert result["attempts"] == 2
        assert mock_create_rlm.call_count == 2

    @patch("rlm_bridge._create_rlm")
    def test_generic_error_is_raised(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.side_effect = Exception("Model unavailable")
        mock_create_rlm.return_value = mock_rlm

        with pytest.raises(Exception) as exc:
            run_rlm(
                query="Test",
                context="Context",
                root_model="kimi-k2.5",
                sub_model="kimi-k2.5",
                base_url="https://api.moonshot.ai/v1",
                api_key="key",
                max_retries=0,
            )

        assert "Model unavailable" in str(exc.value)


class TestMainFallbackFlow:
    @patch("rlm_bridge.run_rlm")
    @patch("rlm_bridge.find_sessions_dir", return_value="/tmp/sessions")
    @patch("rlm_bridge.load_sessions_parallel", new_callable=AsyncMock)
    @patch("rlm_bridge.load_workspace_sync")
    def test_main_attempts_fallback_after_primary_exception(
        self,
        mock_load_workspace,
        mock_load_sessions,
        _mock_find_sessions,
        mock_run_rlm,
    ):
        mock_load_workspace.return_value = "Workspace content " * 20
        mock_load_sessions.return_value = "Session content " * 20

        mock_run_rlm.side_effect = [
            Exception("Primary failure"),
            {
                "response": "Fallback worked",
                "status": "ok",
                "model_used": "kimi-k2-turbo",
                "sub_model_used": "kimi-k2-turbo",
            },
        ]

        test_args = [
            "rlm_bridge.py",
            "--query",
            "Test query",
            "--api-key",
            "test-key",
        ]

        with patch.object(sys, "argv", test_args):
            with patch.object(sys, "stdout", StringIO()) as captured:
                main()

        output = captured.getvalue().strip()
        payload = json.loads(output)

        assert mock_run_rlm.call_count == 2
        second_call = mock_run_rlm.call_args_list[1].kwargs
        assert second_call["root_model"] == "kimi-k2-turbo"
        assert payload["status"] == "ok"
        assert payload["response"] == "Fallback worked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
