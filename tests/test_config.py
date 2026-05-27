from app.core.config import Settings


def test_telegram_credentials_accept_shared_alert_environment_names(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("ALERT_TELEGRAM_TOKEN", "shared-token")
    monkeypatch.setenv("ALERT_TELEGRAM_CHAT_ID", "shared-chat")

    config = Settings(_env_file=None)

    assert config.telegram_bot_token == "shared-token"
    assert config.telegram_chat_id == "shared-chat"
