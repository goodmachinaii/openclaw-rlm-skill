#!/usr/bin/env python3
"""
Tests para verificar comportamiento de fallback cuando el modelo principal falla
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import run_rlm


class TestFallback:
    """Tests para verificar fallback cuando modelo principal falla"""

    @patch("rlm_bridge.RLM")
    def test_rate_limit_retorna_mensaje_amigable(self, mock_rlm_class):
        """Verifica que error 429 retorna mensaje amigable sin re-raise"""
        mock_rlm_instance = MagicMock()
        mock_rlm_instance.completion.side_effect = Exception("Error 429: rate limit exceeded")
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        assert result["status"] == "rate_limited"
        assert "cuota" in result["response"].lower()

    @patch("rlm_bridge.RLM")
    def test_quota_exceeded_retorna_mensaje_amigable(self, mock_rlm_class):
        """Verifica que 'quota exceeded' también se maneja como rate limit"""
        mock_rlm_instance = MagicMock()
        mock_rlm_instance.completion.side_effect = Exception("Quota exceeded for this month")
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        assert result["status"] == "rate_limited"

    @patch("rlm_bridge.RLM")
    def test_error_generico_hace_reraise(self, mock_rlm_class):
        """Verifica que errores genéricos (no rate limit) hacen re-raise para fallback"""
        mock_rlm_instance = MagicMock()
        mock_rlm_instance.completion.side_effect = Exception("Connection timeout")
        mock_rlm_class.return_value = mock_rlm_instance

        with pytest.raises(Exception) as exc_info:
            run_rlm(
                query="Test",
                context="Context",
                root_model="gpt-5.3-codex",
                sub_model="gpt-5.1-codex-mini",
                base_url="http://localhost:8317/v1",
                api_key="key",
            )

        assert "Connection timeout" in str(exc_info.value)

    @patch("rlm_bridge.RLM")
    def test_fallback_se_intenta_tras_error_principal(self, mock_rlm_class):
        """
        Verifica que cuando el modelo principal falla con error genérico,
        main() intentaría el fallback (simulamos el flujo)
        """
        # Este test simula el comportamiento de main() sin ejecutarlo
        call_count = 0
        responses = []

        def mock_rlm_init(**kwargs):
            nonlocal call_count
            call_count += 1
            mock_instance = MagicMock()

            if call_count == 1:
                # Primera llamada (principal) falla
                mock_instance.completion.side_effect = Exception("Model unavailable")
            else:
                # Segunda llamada (fallback) funciona
                mock_result = MagicMock()
                mock_result.response = "Respuesta del fallback"
                mock_instance.completion.return_value = mock_result

            return mock_instance

        mock_rlm_class.side_effect = mock_rlm_init

        # Primera llamada falla
        with pytest.raises(Exception):
            run_rlm(
                query="Test",
                context="Context",
                root_model="gpt-5.3-codex",
                sub_model="gpt-5.1-codex-mini",
                base_url="http://localhost:8317/v1",
                api_key="key",
            )

        # Segunda llamada (fallback) funciona
        result = run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.2",  # Fallback model
            sub_model="gpt-5.2",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        assert result["response"] == "Respuesta del fallback"
        assert result["status"] == "ok"
        assert call_count == 2

    @patch("rlm_bridge.RLM")
    def test_fallback_usa_mismo_modelo_para_root_y_sub(self, mock_rlm_class):
        """
        Verifica que en fallback se usa el mismo modelo para root y sub
        (según el plan: fallback_model se usa para ambos)
        """
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        # Simular llamada de fallback (mismo modelo para root y sub)
        result = run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.2",
            sub_model="gpt-5.2",  # Mismo que root
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        # Verificar que NO se pasó other_backends (porque son iguales)
        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" not in call_kwargs
        assert result["model_used"] == "gpt-5.2"


class TestMainFallbackIntegration:
    """Tests de integración para el flujo completo de fallback en main()"""

    @patch("rlm_bridge.load_workspace")
    @patch("rlm_bridge.load_sessions")
    @patch("rlm_bridge.find_sessions_dir")
    @patch("rlm_bridge.run_rlm")
    def test_main_intenta_fallback_tras_error(
        self, mock_run_rlm, mock_find_sessions, mock_load_sessions, mock_load_workspace
    ):
        """Verifica que main() intenta fallback cuando run_rlm falla"""
        # Setup mocks
        mock_find_sessions.return_value = "/tmp/sessions"
        mock_load_workspace.return_value = "Workspace content"
        mock_load_sessions.return_value = "Session content with enough chars " * 10

        # Primera llamada falla, segunda funciona
        mock_run_rlm.side_effect = [
            Exception("Principal falló"),
            {
                "response": "Fallback funcionó",
                "model_used": "gpt-5.2",
                "sub_model_used": "gpt-5.2",
                "status": "ok",
            }
        ]

        # Importar y ejecutar main con args mockeados
        from rlm_bridge import main
        import sys
        from io import StringIO
        from unittest.mock import patch as context_patch

        test_args = [
            "rlm_bridge.py",
            "--query", "Test query",
        ]

        captured_output = StringIO()
        with context_patch.object(sys, 'argv', test_args):
            with context_patch.object(sys, 'stdout', captured_output):
                main()

        output = captured_output.getvalue()

        # Verificar que run_rlm se llamó 2 veces
        assert mock_run_rlm.call_count == 2

        # Verificar que la segunda llamada usó el modelo fallback
        second_call_kwargs = mock_run_rlm.call_args_list[1].kwargs
        assert second_call_kwargs["root_model"] == "gpt-5.2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
