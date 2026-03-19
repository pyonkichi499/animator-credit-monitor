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

