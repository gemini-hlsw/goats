from goats_cli.config import config, Config

def test_config_addrports():
    """Test that addrport values are generated correctly."""
    assert config.django_addrport == "localhost:8000"
    assert config.redis_addrport == "localhost:6379"

def test_config_custom_values():
    """Test that the Config class correctly handles custom values."""
    cfg = Config(host="127.0.0.1", redis_port=6380, django_port=8080)
    assert cfg.host == "127.0.0.1"
    assert cfg.redis_port == 6380
    assert cfg.django_port == 8080
    assert cfg.django_addrport == "127.0.0.1:8080"
    assert cfg.redis_addrport == "127.0.0.1:6380"