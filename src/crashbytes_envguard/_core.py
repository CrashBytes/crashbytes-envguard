"""Environment variable validation with schema, type coercion, and .env loading."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class EnvError(Exception):
    """Raised when environment validation fails."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        msg = "Environment validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(msg)


@dataclass
class _FieldSpec:
    name: str
    coerce: type[Any]
    required: bool = True
    default: Any = None
    choices: list[Any] = field(default_factory=list)
    min_val: float | None = None
    max_val: float | None = None
    pattern: str | None = None
    custom_name: str | None = None


class SchemaField:
    """Builder for a single environment variable schema field."""

    def __init__(self, coerce: type[Any] = str) -> None:
        self._coerce = coerce
        self._required = True
        self._default: Any = None
        self._choices: list[Any] = []
        self._min_val: float | None = None
        self._max_val: float | None = None
        self._pattern: str | None = None

    def default(self, value: Any) -> SchemaField:
        """Set a default value (makes the field optional)."""
        self._default = value
        self._required = False
        return self

    def optional(self) -> SchemaField:
        """Mark as optional with no default (value will be ``None`` if missing)."""
        self._required = False
        return self

    def choices(self, *values: Any) -> SchemaField:
        """Restrict to a set of allowed values."""
        self._choices = list(values)
        return self

    def min(self, value: float) -> SchemaField:
        """Set minimum value (numeric fields)."""
        self._min_val = value
        return self

    def max(self, value: float) -> SchemaField:
        """Set maximum value (numeric fields)."""
        self._max_val = value
        return self

    def pattern(self, regex: str) -> SchemaField:
        """Require the value to match a regex pattern."""
        self._pattern = regex
        return self

    def _to_spec(self, name: str) -> _FieldSpec:
        return _FieldSpec(
            name=name,
            coerce=self._coerce,
            required=self._required,
            default=self._default,
            choices=self._choices,
            min_val=self._min_val,
            max_val=self._max_val,
            pattern=self._pattern,
        )


class s:  # noqa: N801
    """Schema builder — shorthand for defining field types."""

    @staticmethod
    def string() -> SchemaField:
        return SchemaField(str)

    @staticmethod
    def integer() -> SchemaField:
        return SchemaField(int)

    @staticmethod
    def number() -> SchemaField:
        return SchemaField(float)

    @staticmethod
    def boolean() -> SchemaField:
        return SchemaField(bool)

    @staticmethod
    def port() -> SchemaField:
        """Integer constrained to 1–65535."""
        return SchemaField(int).min(1).max(65535)

    @staticmethod
    def url() -> SchemaField:
        """String that must start with http:// or https://."""
        return SchemaField(str).pattern(r"^https?://")

    @staticmethod
    def email() -> SchemaField:
        """String that must be a valid email format."""
        return SchemaField(str).pattern(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _coerce_bool(raw: str) -> bool:
    low = raw.lower()
    if low in ("true", "1", "yes", "on"):
        return True
    if low in ("false", "0", "no", "off"):
        return False
    raise ValueError(f"Cannot convert {raw!r} to bool")


def _coerce_value(raw: str, target: type[Any]) -> Any:
    if target is bool:
        return _coerce_bool(raw)
    return target(raw)


def load_dotenv(path: str | Path = ".env") -> None:
    """Load variables from a .env file into ``os.environ``."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def create_env(
    schema: dict[str, SchemaField],
    *,
    env_file: str | Path | None = ".env",
) -> dict[str, Any]:
    """Validate environment variables against *schema*.

    Loads from *env_file* first (if it exists), then validates every field.
    Collects **all** errors before raising.

    Returns a dict of coerced values.
    """
    if env_file is not None:
        load_dotenv(env_file)

    errors: list[str] = []
    result: dict[str, Any] = {}

    for name, field_builder in schema.items():
        spec = field_builder._to_spec(name)  # noqa: SLF001
        raw = os.environ.get(name)

        if raw is None or raw == "":
            if spec.required:
                errors.append(f"{name}: required but not set")
                continue
            result[name] = spec.default
            continue

        try:
            value = _coerce_value(raw, spec.coerce)
        except (ValueError, TypeError):
            errors.append(f"{name}: cannot convert {raw!r} to {spec.coerce.__name__}")
            continue

        if spec.choices and value not in spec.choices:
            errors.append(f"{name}: must be one of {spec.choices} (got {value!r})")
            continue

        if spec.min_val is not None and isinstance(value, (int, float)) and value < spec.min_val:
            errors.append(f"{name}: must be >= {spec.min_val} (got {value})")
            continue

        if spec.max_val is not None and isinstance(value, (int, float)) and value > spec.max_val:
            errors.append(f"{name}: must be <= {spec.max_val} (got {value})")
            continue

        if (
            spec.pattern is not None
            and isinstance(value, str)
            and not re.match(spec.pattern, value)
        ):
            errors.append(f"{name}: must match pattern {spec.pattern!r} (got {value!r})")
            continue

        result[name] = value

    if errors:
        raise EnvError(errors)

    return result
