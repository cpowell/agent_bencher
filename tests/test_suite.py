from agent_bencher import __version__


def test_package_import_exposes_version() -> None:
    assert __version__ == "0.1.0"
