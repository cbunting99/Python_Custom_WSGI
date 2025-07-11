# Code Linting and Formatting

This project uses Black for code formatting and Flake8 for linting to maintain consistent code quality.

## Setup

Install the required tools:

```bash
pip install black flake8 pre-commit
```

## Manual Usage

### Format code with Black

```bash
black .
```

### Check code with Flake8

```bash
flake8 .
```

### Run both tools at once

```bash
python lint.py
```

## Automatic Pre-commit Hooks

This project includes pre-commit hooks to automatically run Black and Flake8 before each commit.

To install the pre-commit hooks:

```bash
pre-commit install
```

Once installed, the hooks will run automatically when you commit changes. If any issues are found, the commit will be aborted until you fix them.

## Configuration

- Black and Flake8 settings are configured in `setup.cfg`
- Pre-commit hooks are configured in `.pre-commit-config.yaml`

## CI Integration

These tools are also run in the CI pipeline to ensure code quality. The pipeline will fail if any issues are found.

## Editor Integration

For the best development experience, configure your editor to run Black and Flake8 automatically:

### VS Code

Install the "Python" extension and add these settings to your `settings.json`:

```json
{
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length", "100"],
    "editor.formatOnSave": true,
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.flake8Args": ["--max-line-length=100"]
}
```
