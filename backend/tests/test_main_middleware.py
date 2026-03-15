from app.main import app


def test_gzip_middleware_registered() -> None:
    middleware_names = [middleware.cls.__name__ for middleware in app.user_middleware]
    assert "GZipMiddleware" in middleware_names
