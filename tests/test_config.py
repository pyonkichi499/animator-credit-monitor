from pathlib import Path

import pytest

from animator_credit_monitor.config import ConfigValidationError, load_app_config_from_env


def test_STATE_BACKEND_firestoreではGCP_PROJECT_IDが必須() -> None:
    env = {
        "STATE_BACKEND": "firestore",
        "TARGET_NAME": "テスト",
    }
    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "GCP_PROJECT_ID" in str(exc_info.value)


def test_firestore_backend設定が読み込める() -> None:
    env = {
        "STATE_BACKEND": "firestore",
        "GCP_PROJECT_ID": "proj",
        "FIRESTORE_DATABASE": "(default)",
        "FIRESTORE_COLLECTION_PREFIX": "acm",
        "TARGET_NAME": "テスト",
        "NOTIFIER": "console",
        "NOTIFY_RETRY_MAX_RETRIES": "2",
        "NOTIFY_RETRY_INITIAL_DELAY_SECONDS": "60",
    }
    config = load_app_config_from_env(env)

    assert config.state_backend == "firestore"
    assert config.gcp_project_id == "proj"
    assert config.firestore_collection_prefix == "acm"
    assert config.notify_retry_max_retries == 2
    assert config.notify_retry_initial_delay_seconds == 60


def test_空のenvではデフォルト値で読み込める() -> None:
    config = load_app_config_from_env({})

    assert config.state_backend == "local"
    assert config.notifier_types == ["console"]
    assert config.data_dir == Path("data")
    assert config.firestore_database == "(default)"
    assert config.notify_retry_max_retries == 2
    assert config.notify_retry_initial_delay_seconds == 60
    assert config.email.port == 587
    assert config.email.use_tls is True
    assert config.line.api_url == "https://notify-api.line.me/api/notify"


def test_STATE_BACKENDが不正な値の場合はエラーになる() -> None:
    env = {"STATE_BACKEND": "redis"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "STATE_BACKEND must be one of: local, firestore" in exc_info.value.errors


def test_STATE_BACKENDは大文字や空白を含んでも正規化される() -> None:
    env = {"STATE_BACKEND": "  FIRESTORE  ", "GCP_PROJECT_ID": "proj"}

    config = load_app_config_from_env(env)

    assert config.state_backend == "firestore"


def test_未知のnotifier種別はエラーになる() -> None:
    env = {"NOTIFIER": "slack"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "Notifier type must be one of: console, email, line" in exc_info.value.errors


def test_NOTIFIERSが空文字だけの場合はエラーになる() -> None:
    env = {"NOTIFIERS": " , , "}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "NOTIFIERS is empty" in exc_info.value.errors


def test_notifierの重複指定はエラーになる() -> None:
    env = {"NOTIFIERS": "console,console"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "Duplicate notifier types are not allowed: console" in exc_info.value.errors


def test_NOTIFIERSはカンマ区切りで複数指定でき空白も除去される() -> None:
    env = {
        "NOTIFIERS": " Email , LINE ",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_FROM": "from@example.com",
        "SMTP_TO": "to@example.com",
        "LINE_NOTIFY_TOKEN": "token",
    }

    config = load_app_config_from_env(env)

    assert config.notifier_types == ["email", "line"]


def test_SMTP_PORTが整数でない場合はエラーになる() -> None:
    env = {"SMTP_PORT": "abc"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "SMTP_PORT must be an integer" in exc_info.value.errors


def test_email_notifier指定時はSMTP必須項目が検証される() -> None:
    env = {"NOTIFIER": "email"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "SMTP_HOST, SMTP_FROM, SMTP_TO are required when using email notifier" in exc_info.value.errors


def test_line_notifier指定時はトークンが必須() -> None:
    env = {"NOTIFIER": "line"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "LINE_NOTIFY_TOKEN is required when using line notifier" in exc_info.value.errors


def test_NOTIFY_RETRY_MAX_RETRIESが負数の場合はエラーになる() -> None:
    env = {"NOTIFY_RETRY_MAX_RETRIES": "-1"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "NOTIFY_RETRY_MAX_RETRIES must be an integer >= 0" in exc_info.value.errors


def test_NOTIFY_RETRY_MAX_RETRIESが整数でない場合はエラーになる() -> None:
    env = {"NOTIFY_RETRY_MAX_RETRIES": "many"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "NOTIFY_RETRY_MAX_RETRIES must be an integer >= 0" in exc_info.value.errors


def test_NOTIFY_RETRY_INITIAL_DELAY_SECONDSが負数の場合はエラーになる() -> None:
    env = {"NOTIFY_RETRY_INITIAL_DELAY_SECONDS": "-60"}

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert "NOTIFY_RETRY_INITIAL_DELAY_SECONDS must be an integer >= 0" in exc_info.value.errors


def test_複数の検証エラーがまとめて報告される() -> None:
    env = {
        "STATE_BACKEND": "redis",
        "NOTIFIER": "slack",
        "SMTP_PORT": "abc",
        "NOTIFY_RETRY_MAX_RETRIES": "-1",
    }

    with pytest.raises(ConfigValidationError) as exc_info:
        load_app_config_from_env(env)

    assert len(exc_info.value.errors) == 4


def test_email設定の各項目が読み込まれる() -> None:
    env = {
        "NOTIFIER": "email",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_FROM": "from@example.com",
        "SMTP_TO": "to@example.com",
        "SMTP_USER": "user",
        "SMTP_PASS": "pass",
        "SMTP_USE_TLS": "false",
        "EMAIL_SUBJECT_TEMPLATE": "[通知] {title}",
        "EMAIL_BODY_TEMPLATE": "本文: {message}",
    }

    config = load_app_config_from_env(env)

    assert config.email.host == "smtp.example.com"
    assert config.email.port == 465
    assert config.email.from_addr == "from@example.com"
    assert config.email.to_addr == "to@example.com"
    assert config.email.username == "user"
    assert config.email.password == "pass"
    assert config.email.use_tls is False
    assert config.email.subject_template == "[通知] {title}"
    assert config.email.body_template == "本文: {message}"


def test_line設定の各項目が読み込まれる() -> None:
    env = {
        "NOTIFIER": "line",
        "LINE_NOTIFY_TOKEN": "token",
        "LINE_NOTIFY_API_URL": "https://example.com/notify",
        "LINE_MESSAGE_TEMPLATE": "{title}: {message}",
    }

    config = load_app_config_from_env(env)

    assert config.line.token == "token"
    assert config.line.api_url == "https://example.com/notify"
    assert config.line.message_template == "{title}: {message}"


def test_ターゲット設定とDATA_DIRが読み込まれる() -> None:
    env = {
        "TARGET_BANGUMI_ID": " 12345 ",
        "TARGET_NAME": " 山田太郎 ",
        "DATA_DIR": "custom_data",
    }

    config = load_app_config_from_env(env)

    assert config.bangumi_id == "12345"
    assert config.target_name == "山田太郎"
    assert config.data_dir == Path("custom_data")
