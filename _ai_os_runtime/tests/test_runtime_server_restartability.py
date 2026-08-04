from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_api_server_can_rebind_after_supervised_restart() -> None:
    source = (ROOT / "api" / "ai_os_api_server.py").read_text(encoding="utf-8")
    assert "class AiOsThreadingHTTPServer(ThreadingHTTPServer):" in source
    assert "allow_reuse_address = True" in source
    assert "daemon_threads = True" in source
    assert "server = AiOsThreadingHTTPServer((API_HOST, API_PORT), AiOsApiHandler)" in source


def test_spa_server_can_rebind_after_supervised_restart() -> None:
    source = (ROOT / "scripts" / "serve_spa.py").read_text(encoding="utf-8")
    assert "class ReusableThreadingHTTPServer(ThreadingHTTPServer):" in source
    assert "server = ReusableThreadingHTTPServer((args.host, args.port), SpaRequestHandler)" in source
