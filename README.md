# crashbytes-envguard

Lightweight environment variable validation with schema, type coercion, and .env loading.

## Install

```bash
pip install crashbytes-envguard
```

## Usage

```python
from crashbytes_envguard import create_env, s

env = create_env({
    "PORT": s.port().default(8080),
    "DB_URL": s.url(),
    "DEBUG": s.boolean().default(False),
    "LOG_LEVEL": s.string().choices("debug", "info", "warn", "error").default("info"),
})

print(env["PORT"])      # 8080 (int, type-coerced)
print(env["DB_URL"])    # "https://..." (validated)
print(env["DEBUG"])     # False (bool, type-coerced)
```

Fails fast with **all** errors at once:

```
EnvError: Environment validation failed:
  - DB_URL: required but not set
  - PORT: must be >= 1 (got 0)
```

## Schema Types

| Builder | Type | Extra Validation |
|---------|------|-----------------|
| `s.string()` | `str` | — |
| `s.integer()` | `int` | — |
| `s.number()` | `float` | — |
| `s.boolean()` | `bool` | true/1/yes/on, false/0/no/off |
| `s.port()` | `int` | 1–65535 |
| `s.url()` | `str` | Must start with http(s):// |
| `s.email()` | `str` | Must be valid email format |

## Field Modifiers

`.default(value)`, `.optional()`, `.choices(...)`, `.min(n)`, `.max(n)`, `.pattern(regex)`

## License

MIT
