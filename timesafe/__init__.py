"""time-safe — timelock-encrypt secrets in a GitHub vault.

The version lives here rather than in pyproject.toml because a PyInstaller binary has no installed
package metadata for importlib.metadata to read. hatchling reads it from here, so there is still
exactly one source of truth.
"""

__version__ = "0.1.0"
