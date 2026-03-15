import app.config as config_module


def test_security_warnings_flags_cookie_secure_in_non_debug(monkeypatch):
    monkeypatch.setattr(config_module.settings, "DEBUG", False)
    monkeypatch.setattr(config_module.settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(config_module.settings, "COOKIE_SAMESITE", "lax")
    monkeypatch.setattr(config_module.settings, "CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setattr(config_module.settings, "AUTH_SECRET_KEY", "a" * 32)
    monkeypatch.setattr(config_module.settings, "DEFAULT_ADMIN_PASSWORD", "")

    warnings = config_module.security_warnings()
    assert any("COOKIE_SECURE=false" in item for item in warnings)


def test_security_warnings_flags_invalid_samesite_and_wildcard_cors(monkeypatch):
    monkeypatch.setattr(config_module.settings, "DEBUG", False)
    monkeypatch.setattr(config_module.settings, "COOKIE_SECURE", True)
    monkeypatch.setattr(config_module.settings, "COOKIE_SAMESITE", "invalid")
    monkeypatch.setattr(config_module.settings, "CORS_ORIGINS", "*,http://localhost:3000")
    monkeypatch.setattr(config_module.settings, "AUTH_SECRET_KEY", "a" * 32)
    monkeypatch.setattr(config_module.settings, "DEFAULT_ADMIN_PASSWORD", "")

    warnings = config_module.security_warnings()
    assert any("COOKIE_SAMESITE 配置无效" in item for item in warnings)
    assert any("CORS_ORIGINS 不应包含 *" in item for item in warnings)


def test_security_warnings_flags_none_samesite_without_secure(monkeypatch):
    monkeypatch.setattr(config_module.settings, "DEBUG", False)
    monkeypatch.setattr(config_module.settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(config_module.settings, "COOKIE_SAMESITE", "none")
    monkeypatch.setattr(config_module.settings, "CORS_ORIGINS", "http://localhost:3000")
    monkeypatch.setattr(config_module.settings, "AUTH_SECRET_KEY", "a" * 32)
    monkeypatch.setattr(config_module.settings, "DEFAULT_ADMIN_PASSWORD", "")

    warnings = config_module.security_warnings()
    assert any("COOKIE_SAMESITE=none 时必须启用 COOKIE_SECURE=true" in item for item in warnings)
