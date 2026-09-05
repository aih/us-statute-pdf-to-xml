import pytest

from downloader import config


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("SOME_KEY", " abc ")
    assert config.require_env("SOME_KEY") == "abc"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_require_env_rejects_missing_or_blank(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SOME_KEY", raising=False)
    else:
        monkeypatch.setenv("SOME_KEY", value)
    with pytest.raises(config.MissingEnv) as excinfo:
        config.require_env("SOME_KEY", "hint text")
    assert "SOME_KEY" in str(excinfo.value)
    assert "hint text" in str(excinfo.value)


def test_govinfo_key_has_no_default(monkeypatch):
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    with pytest.raises(config.MissingEnv):
        config.govinfo_api_key()


def test_exit_on_missing_env_exits_with_status_2(monkeypatch, capsys):
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)

    @config.exit_on_missing_env
    def main():
        config.govinfo_api_key()

    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 2
    assert "GOVINFO_API_KEY" in capsys.readouterr().err


def test_scanned_volume_boundary():
    assert config.is_scanned_volume(116)
    assert not config.is_scanned_volume(117)
