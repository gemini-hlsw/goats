import pytest
from goats_cli.config import config
from dataclasses import FrozenInstanceError

def test_config_defaults():
    """Test default values of the Config instance."""
    assert config.host == "localhost"
    assert config.redis_port == 6379
    assert config.django_port == 8000
    assert config.addrport_regex_pattern == r"^(?:(?P<host>[^:]+):)?(?P<port>[0-9]+)$"
    assert config.recopy_exclude_normal == (
        "**",
        "!{{ project_name }}/settings/__init__.py",
        "!{{ project_name }}/settings/base.py",
        "!{{ project_name }}/settings/dynamic.py",
        "!{{ project_name }}/settings/environments/**",
    )
    assert config.recopy_exclude_full == (
        "**",
        "!{{ project_name }}/settings/__init__.py",
        "!{{ project_name }}/settings/base.py",
        "!{{ project_name }}/settings/dynamic.py",
        "!{{ project_name }}/settings/environments/**",
        "!manage.py",
        "!{{ project_name }}/asgi.py",
        "!{{ project_name }}/wsgi.py",
        "!{{ project_name }}/urls.py",
        "!{{ project_name }}/__init__.py",
    )
    assert config.never_overwrite == (
        "{{ project_name }}/settings/local.py",
        "{{ project_name }}/settings/generated.py",
    )
    assert config.update_doc_url == "https://goats.readthedocs.io/en/stable/updating.html"
    assert config.su_username == "admin"
    assert config.su_email == "admin@example.com"


def test_django_addrport():
    """Test the django_addrport property."""
    assert config.django_addrport == "localhost:8000"


def test_redis_addrport():
    """Test the redis_addrport property."""
    assert config.redis_addrport == "localhost:6379"


def test_config_immutability():
    """Test that the Config instance is immutable."""
    with pytest.raises(FrozenInstanceError):
        config.host = "127.0.0.1"
    with pytest.raises(FrozenInstanceError):
        config.redis_port = 6380
    with pytest.raises(FrozenInstanceError):
        config.django_port = 8080
