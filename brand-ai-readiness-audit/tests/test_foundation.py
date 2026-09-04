import sys
import pytest

def test_python_environment():
    """Test that the Python environment is working and modern."""
    assert sys.version_info >= (3, 7), "Python 3.7+ is required"

def test_imports():
    """Test that project packages can be imported."""
    try:
        import audit_shared
        from audit_shared import config
        from audit_shared import logging
        from audit_shared import models
        from audit_shared import crawl
        from audit_shared import extraction
        from audit_shared import rules
        from audit_shared import evidence
        from audit_shared import nlp
        from audit_shared import reporting
    except ImportError as e:
        pytest.fail(f"Failed to import a foundation package: {e}")

def test_config_loading():
    """Test that basic configuration loading works."""
    from audit_shared.config.settings import load_config, AppConfig
    config = load_config()
    assert isinstance(config, AppConfig)
    assert config.crawl.respect_robots_txt is True

def test_entrypoint_import():
    """Test that the project entrypoint can be imported without side effects."""
    try:
        from audit_shared import main
        assert hasattr(main, "run_audit")
    except ImportError as e:
        pytest.fail(f"Failed to import the entrypoint: {e}")
