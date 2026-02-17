#!/usr/bin/env python3
"""
Tests to verify fallback behavior when primary model fails
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import run_rlm


class TestFallback:
    """Tests to verify fallback when primary model fails"""

    @patch("rlm_bridge.RLM")
    def test_rate_limit_returns_friendly_message(self, mock_rlm_class):
        """Verifies 429 error returns friendly message without re-raise"""
        mock_rlm_instance = MagicMock()
        mock_rlm_instance.completion.side_effect = Exception("Error 429: rate limit exceeded")
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        assert result["status"] == "rate_limited"
        assert "rate limit" in result["response"].lower() or "kimi" in result["response"].lower()

    @patch("rlm_bridge.RLM")
    def test_quota_exceeded_returns_friendly_message(self, mock_rlm_class):
        """Verifies 'quota exceeded' is also handled as rate limit"""
        mock_rlm_instance = MagicMock()
        mock_rlm_instance.completion.side_effect = Exception("Quota exceeded for this month")
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-thinking",
            sub_model="kimi-k2.5",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        assert result["status"] == "rate_limited"

    @patch("rlm_bridge.RLM")
    def test_generic_error_raises_for_fallback(self, mock_rlm_class):
        """Verifies generic errors (not rate limit) re-raise for fallback"""
        mock_rlm_instance = MagicMock()
        mock_rlm_instance.completion.side_effect = Exception("Connection timeout")
        mock_rlm_class.return_value = mock_rlm_instance

        with pytest.raises(Exception) as exc_info:
            run_rlm(
                query="Test",
                context="Context",
                root_model="kimi-k2-thinking",
                sub_model="kimi-k2.5",
                base_url="https://api.moonshot.ai/v1",
                api_key="key",
            )

        assert "Connection timeout" in str(exc_info.value)

    @patch("rlm_bridge.RLM")
    def test_fallback_attempted_after_primary_error(self, mock_rlm_class):
        """
        Verifies that when primary model fails with generic error,
        main() would attempt fallback (simulating the flow)
        """
        # This test simulates main() behavior without executing it
        call_count = 0
        responses = []

        def mock_rlm_init(**kwargs):
            nonlocal call_count
            call_count += 1
            mock_instance = MagicMock()

            if call_count == 1:
                # First call (primary) fails
                mock_instance.completion.side_effect = Exception("Model unavailable")
            else:
                # Second call (fallback) works
                mock_result = MagicMock()
                mock_result.response = "Fallback response"
                mock_instance.completion.return_value = mock_result

            return mock_instance

        mock_rlm_class.side_effect = mock_rlm_init

        # First call fails
        with pytest.raises(Exception):
            run_rlm(
                query="Test",
                context="Context",
                root_model="kimi-k2-thinking",
                sub_model="kimi-k2.5",
                base_url="https://api.moonshot.ai/v1",
                api_key="key",
            )

        # Second call (fallback) works
        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-turbo",  # Fallback model
            sub_model="kimi-k2-turbo",
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        assert result["response"] == "Fallback response"
        assert result["status"] == "ok"
        assert call_count == 2

    @patch("rlm_bridge.RLM")
    def test_fallback_uses_same_model_for_root_and_sub(self, mock_rlm_class):
        """
        Verifies that fallback uses same model for root and sub
        (per plan: fallback_model is used for both)
        """
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        # Simulate fallback call (same model for root and sub)
        result = run_rlm(
            query="Test",
            context="Context",
            root_model="kimi-k2-turbo",
            sub_model="kimi-k2-turbo",  # Same as root
            base_url="https://api.moonshot.ai/v1",
            api_key="key",
        )

        # Verify other_backends was NOT passed (because they're equal)
        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" not in call_kwargs
        assert result["model_used"] == "kimi-k2-turbo"


class TestMainFallbackIntegration:
    """Integration tests for complete fallback flow in main()"""

    @patch("rlm_bridge.load_workspace")
    @patch("rlm_bridge.load_sessions")
    @patch("rlm_bridge.find_sessions_dir")
    @patch("rlm_bridge.run_rlm")
    def test_main_attempts_fallback_after_error(
        self, mock_run_rlm, mock_find_sessions, mock_load_sessions, mock_load_workspace
    ):
        """Verifies main() attempts fallback when run_rlm fails"""
        # Setup mocks
        mock_find_sessions.return_value = "/tmp/sessions"
        mock_load_workspace.return_value = "Workspace content"
        mock_load_sessions.return_value = "Session content with enough chars " * 10

        # First call fails, second works
        mock_run_rlm.side_effect = [
            Exception("Primary failed"),
            {
                "response": "Fallback worked",
                "model_used": "kimi-k2-turbo",
                "sub_model_used": "kimi-k2-turbo",
                "status": "ok",
            }
        ]

        # Import and execute main with mocked args
        from rlm_bridge import main
        import sys
        from io import StringIO
        from unittest.mock import patch as context_patch

        test_args = [
            "rlm_bridge.py",
            "--query", "Test query",
            "--api-key", "test-key",
        ]

        captured_output = StringIO()
        with context_patch.object(sys, 'argv', test_args):
            with context_patch.object(sys, 'stdout', captured_output):
                main()

        output = captured_output.getvalue()

        # Verify run_rlm was called 2 times
        assert mock_run_rlm.call_count == 2

        # Verify second call used fallback model
        second_call_kwargs = mock_run_rlm.call_args_list[1].kwargs
        assert second_call_kwargs["root_model"] == "kimi-k2-turbo"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
