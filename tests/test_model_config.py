#!/usr/bin/env python3
"""
Tests to verify model configuration in run_rlm()
Verifies other_backends is passed correctly when root != sub model
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import run_rlm


class TestRunRlmModels:
    """Tests to verify model configuration in run_rlm()"""

    @patch("rlm_bridge.RLM")
    def test_other_backends_when_models_different(self, mock_rlm_class):
        """Verifies other_backends is configured when root != sub model"""
        # Setup mock
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Test response"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        # Execute with different models (Kimi)
        result = run_rlm(
            query="What did we do yesterday?",
            context="Test context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",  # Different from root
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
        )

        # Verify RLM was called with other_backends
        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" in call_kwargs
        assert call_kwargs["other_backends"] == ["openai"]
        assert "other_backend_kwargs" in call_kwargs
        assert call_kwargs["other_backend_kwargs"][0]["model_name"] == "kimi-k2.5"

    @patch("rlm_bridge.RLM")
    def test_no_other_backends_when_models_same(self, mock_rlm_class):
        """Verifies other_backends is NOT configured when root == sub model"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Response"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        # Execute with same model
        result = run_rlm(
            query="Question",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2-thinking",  # Same as root
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
        )

        # Verify other_backends was NOT passed
        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" not in call_kwargs
        assert "other_backend_kwargs" not in call_kwargs

    @patch("rlm_bridge.RLM")
    def test_no_other_backends_when_sub_model_none(self, mock_rlm_class):
        """Verifies other_backends is NOT configured when sub_model is None"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Response"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Question",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model=None,
            base_url="https://api.moonshot.ai/v1",
            api_key="test-key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" not in call_kwargs

    @patch("rlm_bridge.RLM")
    def test_backend_kwargs_contains_base_url(self, mock_rlm_class):
        """Verifies backend_kwargs includes base_url for Moonshot API"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        custom_url = "https://api.moonshot.cn/v1"
        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url=custom_url,
            api_key="my-key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["backend_kwargs"]["base_url"] == custom_url
        assert call_kwargs["backend_kwargs"]["api_key"] == "my-key"

    @patch("rlm_bridge.RLM")
    def test_max_iterations_is_20(self, mock_rlm_class):
        """Verifies max_iterations is set to 20 (reduced from default 30)"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["max_iterations"] == 20

    @patch("rlm_bridge.RLM")
    def test_max_depth_is_1(self, mock_rlm_class):
        """Verifies max_depth is 1 (only functional value per RLM docs)"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["max_depth"] == 1

    @patch("rlm_bridge.RLM")
    def test_environment_is_local(self, mock_rlm_class):
        """Verifies environment is 'local' (REPL runs locally)"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["environment"] == "local"

    @patch("rlm_bridge.RLM")
    def test_result_includes_models_used(self, mock_rlm_class):
        """Verifies result includes which models were used"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Analysis complete"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Analyze",
            context="Data",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        assert result["model_used"] == "kimi-k2-thinking"
        assert result["sub_model_used"] == "kimi-k2.5"
        assert result["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
