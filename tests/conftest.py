import os, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_USAGE_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("CLAUDE_USAGE_CACHE", str(tmp_path / "cache"))
    yield tmp_path
