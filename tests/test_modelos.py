#!/usr/bin/env python3
"""
Tests para verificar configuración de modelos en run_rlm()
Verifica que other_backends se pasa correctamente cuando root != sub model
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import run_rlm


class TestRunRlmModelos:
    """Tests para verificar configuración de modelos en run_rlm()"""

    @patch("rlm_bridge.RLM")
    def test_other_backends_cuando_modelos_diferentes(self, mock_rlm_class):
        """Verifica que other_backends se configura cuando root != sub model"""
        # Setup mock
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Respuesta de prueba"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        # Ejecutar con modelos diferentes
        result = run_rlm(
            query="¿Qué hicimos ayer?",
            context="Contexto de prueba",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",  # Diferente al root
            base_url="http://localhost:8317/v1",
            api_key="test-key",
        )

        # Verificar que RLM se llamó con other_backends
        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" in call_kwargs
        assert call_kwargs["other_backends"] == ["openai"]
        assert "other_backend_kwargs" in call_kwargs
        assert call_kwargs["other_backend_kwargs"][0]["model_name"] == "gpt-5.1-codex-mini"

    @patch("rlm_bridge.RLM")
    def test_sin_other_backends_cuando_modelos_iguales(self, mock_rlm_class):
        """Verifica que other_backends NO se configura cuando root == sub model"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Respuesta"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        # Ejecutar con mismo modelo
        result = run_rlm(
            query="Pregunta",
            context="Contexto",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.3-codex",  # Igual al root
            base_url="http://localhost:8317/v1",
            api_key="test-key",
        )

        # Verificar que NO se pasó other_backends
        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" not in call_kwargs
        assert "other_backend_kwargs" not in call_kwargs

    @patch("rlm_bridge.RLM")
    def test_sin_other_backends_cuando_sub_model_none(self, mock_rlm_class):
        """Verifica que other_backends NO se configura cuando sub_model es None"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Respuesta"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Pregunta",
            context="Contexto",
            root_model="gpt-5.3-codex",
            sub_model=None,
            base_url="http://localhost:8317/v1",
            api_key="test-key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert "other_backends" not in call_kwargs

    @patch("rlm_bridge.RLM")
    def test_backend_kwargs_contiene_base_url(self, mock_rlm_class):
        """Verifica que backend_kwargs incluye base_url para CLIProxyAPI"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        custom_url = "http://192.168.1.100:8317/v1"
        result = run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url=custom_url,
            api_key="my-key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["backend_kwargs"]["base_url"] == custom_url
        assert call_kwargs["backend_kwargs"]["api_key"] == "my-key"

    @patch("rlm_bridge.RLM")
    def test_max_iterations_es_20(self, mock_rlm_class):
        """Verifica que max_iterations está configurado a 20 (reducido del default 30)"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["max_iterations"] == 20

    @patch("rlm_bridge.RLM")
    def test_max_depth_es_1(self, mock_rlm_class):
        """Verifica que max_depth es 1 (único valor funcional según docs RLM)"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["max_depth"] == 1

    @patch("rlm_bridge.RLM")
    def test_environment_es_local(self, mock_rlm_class):
        """Verifica que environment es 'local' (REPL corre en Pi directamente)"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "OK"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        run_rlm(
            query="Test",
            context="Context",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        call_kwargs = mock_rlm_class.call_args.kwargs
        assert call_kwargs["environment"] == "local"

    @patch("rlm_bridge.RLM")
    def test_resultado_incluye_modelos_usados(self, mock_rlm_class):
        """Verifica que el resultado incluye qué modelos se usaron"""
        mock_rlm_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Análisis completado"
        mock_rlm_instance.completion.return_value = mock_result
        mock_rlm_class.return_value = mock_rlm_instance

        result = run_rlm(
            query="Analiza",
            context="Datos",
            root_model="gpt-5.3-codex",
            sub_model="gpt-5.1-codex-mini",
            base_url="http://localhost:8317/v1",
            api_key="key",
        )

        assert result["model_used"] == "gpt-5.3-codex"
        assert result["sub_model_used"] == "gpt-5.1-codex-mini"
        assert result["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
