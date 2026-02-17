#!/usr/bin/env python3
"""Tests for profile resolution in main()."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import main


@patch("rlm_bridge.run_rlm")
@patch("rlm_bridge.find_sessions_dir", return_value="/tmp/sessions")
@patch("rlm_bridge.load_sessions_parallel", new_callable=AsyncMock)
@patch("rlm_bridge.load_workspace_sync")
def test_speed_and_pi_profiles_are_applied(
    mock_load_workspace,
    mock_load_sessions,
    _mock_find_sessions,
    mock_run_rlm,
):
    mock_load_workspace.return_value = "Workspace content " * 20
    mock_load_sessions.return_value = "Session content " * 20
    mock_run_rlm.return_value = {
        "response": "ok",
        "status": "ok",
        "model_used": "kimi-k2.5",
        "sub_model_used": "kimi-k2-turbo-preview",
    }

    test_args = [
        "rlm_bridge.py",
        "--query",
        "Test query",
        "--api-key",
        "test-key",
        "--profile-model",
        "speed",
        "--pi-profile",
        "pi4",
    ]

    with patch.object(sys, "argv", test_args):
        with patch.object(sys, "stdout", StringIO()) as captured:
            main()

    payload = json.loads(captured.getvalue().strip())

    call_kwargs = mock_run_rlm.call_args.kwargs
    assert call_kwargs["root_model"] == "kimi-k2.5"
    assert call_kwargs["sub_model"] == "kimi-k2-turbo-preview"
    assert call_kwargs["max_iterations"] == 4
    assert call_kwargs["compaction"] is True

    resolved = payload["resolved_config"]
    assert resolved["model_profile"] == "speed"
    assert resolved["pi_profile"] == "pi4"
    assert resolved["sub_model"] == "kimi-k2-turbo-preview"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
