#!/usr/bin/env python3
"""
Tests for model configuration in run_rlm().
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import run_rlm


def _mock_result(response: str = "ok"):
    usage = MagicMock()
    usage.to_dict.return_value = {
        "model_usage_summaries": {
            "kimi-k2.5": {
                "total_calls": 1,
                "total_input_tokens": 1000,
                "total_output_tokens": 500,
            }
        }
    }
    return SimpleNamespace(response=response, execution_time=1.23, usage_summary=usage)


class TestRunRlmModels:
    @patch("rlm_bridge._create_rlm")
    def test_other_backends_when_models_different(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.return_value = _mock_result()
        mock_create_rlm.return_value = mock_rlm

        run_rlm(
            query="What did we do yesterday?",
            context="Test context",
            root_model="kimi-k2.5",
            sub_model="kimi-k2-turbo-preview",
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
        )

        kwargs = mock_create_rlm.call_args.kwargs
        assert kwargs["backend_kwargs"]["model_name"] == "kimi-k2.5"
        assert kwargs["other_backends"] == ["openai"]
        assert kwargs["other_backend_kwargs"][0]["model_name"] == "kimi-k2-turbo-preview"

    @patch("rlm_bridge._create_rlm")
    def test_no_other_backends_when_models_same(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.return_value = _mock_result()
        mock_create_rlm.return_value = mock_rlm

        run_rlm(
            query="Question",
            context="Context",
            root_model="kimi-k2.5",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
        )

        kwargs = mock_create_rlm.call_args.kwargs
        assert "other_backends" not in kwargs
        assert "other_backend_kwargs" not in kwargs

    @patch("rlm_bridge._create_rlm")
    def test_max_iterations_and_compaction_configuration(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.return_value = _mock_result()
        mock_create_rlm.return_value = mock_rlm

        run_rlm(
            query="Question",
            context="Context",
            root_model="kimi-k2.5",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
            max_iterations=7,
            compaction=True,
            compaction_threshold=0.75,
        )

        kwargs = mock_create_rlm.call_args.kwargs
        assert kwargs["max_iterations"] == 7
        assert kwargs["compaction"] is True
        assert kwargs["compaction_threshold_pct"] == 0.75
        assert kwargs["max_depth"] == 1

    @patch("rlm_bridge._create_rlm")
    def test_request_timeout_in_backend_kwargs(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.return_value = _mock_result()
        mock_create_rlm.return_value = mock_rlm

        run_rlm(
            query="Question",
            context="Context",
            root_model="kimi-k2.5",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
            request_timeout=45.0,
        )

        kwargs = mock_create_rlm.call_args.kwargs
        assert kwargs["backend_kwargs"]["timeout"] == 45.0

    @patch("rlm_bridge._create_rlm")
    def test_result_includes_cost_estimate(self, mock_create_rlm):
        mock_rlm = MagicMock()
        mock_rlm.completion.return_value = _mock_result(response="Analysis complete")
        mock_create_rlm.return_value = mock_rlm

        result = run_rlm(
            query="Analyze",
            context="Data",
            root_model="kimi-k2.5",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
        )

        assert result["status"] == "ok"
        assert result["response"] == "Analysis complete"
        assert result["cost_estimate"]["total_estimated_usd"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
