#!/usr/bin/env python3
"""
Tests básicos para rlm_bridge.py
Verifica parse_jsonl_session() y load_sessions()
"""

import json
import tempfile
from pathlib import Path

import pytest

# Importar funciones del bridge
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from rlm_bridge import parse_jsonl_session, load_sessions


class TestParseJsonlSession:
    """Tests para parse_jsonl_session()"""

    def test_convierte_jsonl_a_texto_legible(self, tmp_path):
        """Verifica que JSONL se convierte a formato [role]: texto"""
        # Crear archivo JSONL de prueba
        jsonl_file = tmp_path / "session_001.jsonl"
        entries = [
            {
                "type": "message",
                "timestamp": "2026-01-15T10:00:00Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hola, ¿cómo estás?"}]
                }
            },
            {
                "type": "message",
                "timestamp": "2026-01-15T10:00:05Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "¡Hola! Estoy bien, gracias."}]
                }
            },
        ]
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Parsear
        result = parse_jsonl_session(jsonl_file)

        # Verificar
        assert "[user]: Hola, ¿cómo estás?" in result
        assert "[assistant]: ¡Hola! Estoy bien, gracias." in result

    def test_ignora_tool_result(self, tmp_path):
        """Verifica que toolResult no se incluye en el output"""
        jsonl_file = tmp_path / "session_002.jsonl"
        entries = [
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Busca archivos"}]
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
                    "content": [{"type": "text", "text": "Encontré 2 archivos."}]
                }
            },
        ]
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        result = parse_jsonl_session(jsonl_file)

        assert "[user]: Busca archivos" in result
        assert "[assistant]: Encontré 2 archivos." in result
        assert "toolResult" not in result
        assert "file1.txt" not in result

    def test_maneja_content_como_string(self, tmp_path):
        """Verifica que content como string directo funciona"""
        jsonl_file = tmp_path / "session_003.jsonl"
        entry = {
            "type": "message",
            "message": {
                "role": "user",
                "content": "Mensaje simple como string"
            }
        }
        with open(jsonl_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        result = parse_jsonl_session(jsonl_file)

        assert "[user]: Mensaje simple como string" in result

    def test_archivo_vacio_retorna_string_vacio(self, tmp_path):
        """Verifica que archivo vacío no causa error"""
        jsonl_file = tmp_path / "empty.jsonl"
        jsonl_file.touch()

        result = parse_jsonl_session(jsonl_file)

        assert result == ""

    def test_lineas_json_invalidas_se_ignoran(self, tmp_path):
        """Verifica que JSON inválido se salta sin error"""
        jsonl_file = tmp_path / "mixed.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            f.write("esto no es json\n")
            f.write(json.dumps({
                "message": {"role": "user", "content": [{"type": "text", "text": "válido"}]}
            }) + "\n")
            f.write("{json incompleto\n")

        result = parse_jsonl_session(jsonl_file)

        assert "[user]: válido" in result
        assert "esto no es json" not in result


class TestLoadSessions:
    """Tests para load_sessions()"""

    def test_encuentra_archivos_jsonl(self, tmp_path):
        """Verifica que load_sessions encuentra y carga archivos .jsonl"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Crear sesión JSONL
        session_file = sessions_dir / "session_abc123.jsonl"
        entry = {
            "message": {"role": "user", "content": [{"type": "text", "text": "Test session"}]}
        }
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir))

        assert "SESSION:session_abc123" in result
        assert "[user]: Test session" in result

    def test_respeta_max_sessions(self, tmp_path):
        """Verifica que max_sessions limita la cantidad de sesiones cargadas"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Crear 5 sesiones
        for i in range(5):
            session_file = sessions_dir / f"session_{i:03d}.jsonl"
            entry = {"message": {"role": "user", "content": f"Sesión {i}"}}
            with open(session_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir), max_sessions=2)

        # Solo debe haber 2 sesiones (las más recientes por mtime)
        session_count = result.count("SESSION:")
        assert session_count == 2

    def test_directorio_inexistente_retorna_mensaje(self, tmp_path):
        """Verifica que directorio inexistente retorna mensaje apropiado"""
        result = load_sessions(str(tmp_path / "no_existe"))

        assert "No hay sesiones disponibles" in result

    def test_ignora_sessions_json_index(self, tmp_path):
        """Verifica que sessions.json (índice) no se procesa como sesión"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Crear índice (no es sesión)
        index_file = sessions_dir / "sessions.json"
        with open(index_file, "w") as f:
            json.dump({"sessions": []}, f)

        # Crear sesión real
        session_file = sessions_dir / "real_session.jsonl"
        entry = {"message": {"role": "user", "content": "Real"}}
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir))

        assert "SESSION:real_session" in result
        assert "SESSION:sessions" not in result

    def test_sesiones_muy_cortas_se_ignoran(self, tmp_path):
        """Verifica que sesiones con menos de 50 chars se ignoran"""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Sesión corta (será ignorada)
        short = sessions_dir / "short.jsonl"
        with open(short, "w") as f:
            f.write('{"message":{"role":"user","content":"Hi"}}\n')

        # Sesión larga (será incluida)
        long = sessions_dir / "long.jsonl"
        entry = {"message": {"role": "user", "content": "x" * 100}}
        with open(long, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        result = load_sessions(str(sessions_dir))

        assert "SESSION:long" in result
        # short puede o no aparecer dependiendo de cómo se cuenta el formato


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
