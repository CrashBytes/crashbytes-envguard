"""Tests for crashbytes-envguard."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from crashbytes_envguard import EnvError, create_env, load_dotenv, s


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove test env vars before each test."""
    for key in ["PORT", "DB_URL", "DEBUG", "APP_NAME", "HOST", "WORKERS", "LOG_LEVEL", "EMAIL"]:
        monkeypatch.delenv(key, raising=False)


class TestSchemaTypes:
    def test_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NAME", "myapp")
        result = create_env({"APP_NAME": s.string()}, env_file=None)
        assert result["APP_NAME"] == "myapp"

    def test_integer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "8080")
        result = create_env({"PORT": s.integer()}, env_file=None)
        assert result["PORT"] == 8080

    def test_number(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WORKERS", "3.5")
        result = create_env({"WORKERS": s.number()}, env_file=None)
        assert result["WORKERS"] == 3.5

    def test_boolean_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for val in ["true", "1", "yes", "on", "True", "YES"]:
            monkeypatch.setenv("DEBUG", val)
            result = create_env({"DEBUG": s.boolean()}, env_file=None)
            assert result["DEBUG"] is True

    def test_boolean_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for val in ["false", "0", "no", "off", "False", "NO"]:
            monkeypatch.setenv("DEBUG", val)
            result = create_env({"DEBUG": s.boolean()}, env_file=None)
            assert result["DEBUG"] is False

    def test_boolean_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEBUG", "maybe")
        with pytest.raises(EnvError, match="cannot convert"):
            create_env({"DEBUG": s.boolean()}, env_file=None)

    def test_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "443")
        result = create_env({"PORT": s.port()}, env_file=None)
        assert result["PORT"] == 443

    def test_port_out_of_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "99999")
        with pytest.raises(EnvError, match="must be <="):
            create_env({"PORT": s.port()}, env_file=None)

    def test_port_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "0")
        with pytest.raises(EnvError, match="must be >="):
            create_env({"PORT": s.port()}, env_file=None)

    def test_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DB_URL", "https://db.example.com")
        result = create_env({"DB_URL": s.url()}, env_file=None)
        assert result["DB_URL"] == "https://db.example.com"

    def test_url_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DB_URL", "ftp://nope")
        with pytest.raises(EnvError, match="must match pattern"):
            create_env({"DB_URL": s.url()}, env_file=None)

    def test_email(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL", "user@example.com")
        result = create_env({"EMAIL": s.email()}, env_file=None)
        assert result["EMAIL"] == "user@example.com"

    def test_email_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL", "not-an-email")
        with pytest.raises(EnvError, match="must match pattern"):
            create_env({"EMAIL": s.email()}, env_file=None)


class TestDefaults:
    def test_default_value(self) -> None:
        result = create_env({"PORT": s.port().default(8080)}, env_file=None)
        assert result["PORT"] == 8080

    def test_optional_none(self) -> None:
        result = create_env({"HOST": s.string().optional()}, env_file=None)
        assert result["HOST"] is None

    def test_env_overrides_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "3000")
        result = create_env({"PORT": s.port().default(8080)}, env_file=None)
        assert result["PORT"] == 3000


class TestValidation:
    def test_required_missing(self) -> None:
        with pytest.raises(EnvError, match="required but not set"):
            create_env({"PORT": s.port()}, env_file=None)

    def test_empty_string_treated_as_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "")
        with pytest.raises(EnvError, match="required but not set"):
            create_env({"PORT": s.port()}, env_file=None)

    def test_choices(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "info")
        result = create_env(
            {"LOG_LEVEL": s.string().choices("debug", "info", "warn", "error")},
            env_file=None,
        )
        assert result["LOG_LEVEL"] == "info"

    def test_choices_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "verbose")
        with pytest.raises(EnvError, match="must be one of"):
            create_env(
                {"LOG_LEVEL": s.string().choices("debug", "info", "warn", "error")},
                env_file=None,
            )

    def test_min_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WORKERS", "4")
        result = create_env(
            {"WORKERS": s.integer().min(1).max(16)},
            env_file=None,
        )
        assert result["WORKERS"] == 4

    def test_pattern(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST", "abc123")
        result = create_env(
            {"HOST": s.string().pattern(r"^[a-z0-9]+$")},
            env_file=None,
        )
        assert result["HOST"] == "abc123"

    def test_pattern_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST", "ABC!")
        with pytest.raises(EnvError, match="must match pattern"):
            create_env(
                {"HOST": s.string().pattern(r"^[a-z0-9]+$")},
                env_file=None,
            )

    def test_coerce_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "abc")
        with pytest.raises(EnvError, match="cannot convert"):
            create_env({"PORT": s.integer()}, env_file=None)

    def test_multiple_errors(self) -> None:
        with pytest.raises(EnvError) as exc_info:
            create_env(
                {"PORT": s.port(), "DB_URL": s.url()},
                env_file=None,
            )
        assert len(exc_info.value.errors) == 2


class TestDotEnv:
    def test_load_dotenv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text('PORT=9090\nAPP_NAME="my app"\n')
        monkeypatch.delenv("PORT", raising=False)
        monkeypatch.delenv("APP_NAME", raising=False)
        load_dotenv(env_file)
        assert os.environ.get("PORT") == "9090"
        assert os.environ.get("APP_NAME") == "my app"

    def test_dotenv_with_comments(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nPORT=8080\n\n")
        monkeypatch.delenv("PORT", raising=False)
        load_dotenv(env_file)
        assert os.environ.get("PORT") == "8080"

    def test_dotenv_single_quotes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("APP_NAME='my app'\n")
        monkeypatch.delenv("APP_NAME", raising=False)
        load_dotenv(env_file)
        assert os.environ.get("APP_NAME") == "my app"

    def test_dotenv_missing_file(self) -> None:
        load_dotenv("/nonexistent/.env")  # Should not raise

    def test_dotenv_no_equals(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("NOPE\n")
        load_dotenv(env_file)  # Should skip lines without =

    def test_dotenv_does_not_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("PORT=9090\n")
        monkeypatch.setenv("PORT", "3000")
        load_dotenv(env_file)
        assert os.environ.get("PORT") == "3000"

    def test_create_env_with_dotenv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("PORT=4000\n")
        monkeypatch.delenv("PORT", raising=False)
        result = create_env({"PORT": s.port()}, env_file=env_file)
        assert result["PORT"] == 4000


class TestEnvError:
    def test_error_message(self) -> None:
        err = EnvError(["PORT: required", "DB_URL: required"])
        assert "PORT: required" in str(err)
        assert "DB_URL: required" in str(err)
        assert len(err.errors) == 2
