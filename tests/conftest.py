import os, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("CLAUDE_USAGE_CACHE", str(tmp_path / "cache"))
    # never touch the real Keychain or network from tests
    from claude_usage import quota
    monkeypatch.setattr(quota, "read_token", lambda: None)
    monkeypatch.setattr(quota, "http_get", lambda token: (0, ""))
    yield tmp_path
