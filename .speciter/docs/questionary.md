# Questionary

Current published docs found: `questionary` `2.0.1`.

Docs:
- https://questionary.readthedocs.io/en/stable/pages/quickstart.html
- https://questionary.readthedocs.io/en/stable/pages/types.html
- https://questionary.readthedocs.io/en/stable/pages/api_reference.html
- https://questionary.readthedocs.io/en/stable/_modules/questionary/prompt.html

## Single prompts

```python
import questionary

name = questionary.text("Workspace name").ask()

provider = questionary.select(
    "Embedding provider",
    choices=["openai", "openrouter", "local"],
    default="openrouter",
).ask()

api_key = questionary.password("API key").ask()
```

## Validation

```python
import questionary

endpoint = questionary.text(
    "Base URL",
    validate=lambda text: bool(text.strip()) or "URL is required",
).ask()

api_key = questionary.password(
    "API key",
    validate=lambda text: len(text) >= 10 or "Key looks too short",
).ask()
```

## Multi-question config flow

```python
import questionary

answers = questionary.form(
    provider=questionary.select(
        "Provider",
        choices=["openrouter", "local"],
    ),
    model=questionary.text("Embedding model"),
).ask()
```

## Conditional prompting with `prompt()`

Use `questionary.prompt([...])` when later questions depend on earlier answers.

```python
import questionary

questions = [
    {
        "type": "select",
        "name": "provider",
        "message": "Provider",
        "choices": ["openrouter", "local"],
    },
    {
        "type": "password",
        "name": "api_key",
        "message": "OpenRouter API key",
        "when": lambda answers: answers["provider"] == "openrouter",
    },
    {
        "type": "text",
        "name": "base_url",
        "message": "Local server URL",
        "default": "http://localhost:11434",
        "when": lambda answers: answers["provider"] == "local",
    },
]

answers = questionary.prompt(questions)
```

## Dynamic defaults and choices

Docs/source show `prompt()` also supports callable `default` and callable `choices`.

```python
import questionary

questions = [
    {
        "type": "select",
        "name": "provider",
        "message": "Provider",
        "choices": ["openai", "openrouter"],
    },
    {
        "type": "select",
        "name": "model",
        "message": "Model",
        "choices": lambda answers: (
            ["text-embedding-3-small", "text-embedding-3-large"]
            if answers["provider"] == "openai"
            else ["openai/text-embedding-3-small", "cohere/embed-english-v3.0"]
        ),
        "default": lambda answers: (
            "text-embedding-3-small"
            if answers["provider"] == "openai"
            else "openai/text-embedding-3-small"
        ),
    },
]

answers = questionary.prompt(questions)
```

## Single-question branching with `skip_if()`

For one-off branching outside `prompt([...])`:

```python
import questionary

use_auth = questionary.select("Use auth?", choices=["yes", "no"]).ask() == "yes"

api_key = questionary.password("API key").skip_if(not use_auth, default=None).ask()
```

## Practical CLI config example

```python
import questionary

answers = questionary.prompt([
    {
        "type": "text",
        "name": "workspace",
        "message": "Workspace name",
        "validate": lambda text: bool(text.strip()) or "Required",
    },
    {
        "type": "select",
        "name": "provider",
        "message": "Embedding provider",
        "choices": ["openrouter", "local"],
    },
    {
        "type": "text",
        "name": "model",
        "message": "Embedding model",
        "default": lambda a: (
            "openai/text-embedding-3-small"
            if a["provider"] == "openrouter"
            else "nomic-embed-text"
        ),
    },
    {
        "type": "password",
        "name": "api_key",
        "message": "OpenRouter API key",
        "when": lambda a: a["provider"] == "openrouter",
    },
    {
        "type": "text",
        "name": "base_url",
        "message": "Local base URL",
        "default": "http://localhost:11434",
        "when": lambda a: a["provider"] == "local",
    },
])
```

## Notes

- `text(...)`, `password(...)`, and `select(...)` return a `Question`; call `.ask()`.
- `form(...)` is good for fixed flows.
- `prompt([...])` is the documented path for conditional CLI flows via `when(answers)`.
- `prompt([...])` also supports `filter`, callable `default`, and callable `choices`.
