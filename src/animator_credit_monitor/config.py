from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    from_addr: str
    to_addr: str
    username: str
    password: str
    use_tls: bool
    subject_template: str
    body_template: str


@dataclass(frozen=True)
class LineConfig:
    token: str
    api_url: str
    message_template: str


@dataclass(frozen=True)
class AppConfig:
    state_backend: str
    bangumi_id: str
    target_name: str
    data_dir: Path
    notifier_types: list[str]
    gcp_project_id: str
    firestore_database: str
    firestore_collection_prefix: str
    notify_retry_max_retries: int
    notify_retry_initial_delay_seconds: int
    email: EmailConfig
    line: LineConfig


class ConfigValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def _parse_notifier_types(env: dict[str, str]) -> list[str]:
    raw_multi = env.get("NOTIFIERS", "").strip()
    if raw_multi:
        return [v.strip().lower() for v in raw_multi.split(",") if v.strip()]

    raw_single = env.get("NOTIFIER", "console").strip().lower()
    return [raw_single]


def _parse_bool(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_app_config_from_env(env: dict[str, str]) -> AppConfig:
    state_backend = env.get("STATE_BACKEND", "local").strip().lower() or "local"
    notifier_types = _parse_notifier_types(env)
    errors: list[str] = []

    if state_backend not in {"local", "firestore"}:
        errors.append("STATE_BACKEND must be one of: local, firestore")

    if not notifier_types:
        errors.append("NOTIFIERS is empty")

    allowed_notifiers = {"console", "email", "line"}
    unknown = [n for n in notifier_types if n not in allowed_notifiers]
    if unknown:
        errors.append("Notifier type must be one of: console, email, line")

    duplicates = sorted({n for n in notifier_types if notifier_types.count(n) > 1})
    if duplicates:
        errors.append(f"Duplicate notifier types are not allowed: {', '.join(duplicates)}")

    smtp_port_raw = env.get("SMTP_PORT", "587").strip()
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587
        errors.append("SMTP_PORT must be an integer")

    email = EmailConfig(
        host=env.get("SMTP_HOST", "").strip(),
        port=smtp_port,
        from_addr=env.get("SMTP_FROM", "").strip(),
        to_addr=env.get("SMTP_TO", "").strip(),
        username=env.get("SMTP_USER", "").strip(),
        password=env.get("SMTP_PASS", "").strip(),
        use_tls=_parse_bool(env.get("SMTP_USE_TLS", "true"), default=True),
        subject_template=env.get("EMAIL_SUBJECT_TEMPLATE", "{title}"),
        body_template=env.get("EMAIL_BODY_TEMPLATE", "{message}"),
    )
    line = LineConfig(
        token=env.get("LINE_NOTIFY_TOKEN", "").strip(),
        api_url=env.get("LINE_NOTIFY_API_URL", "").strip() or "https://notify-api.line.me/api/notify",
        message_template=env.get("LINE_MESSAGE_TEMPLATE", "{title}\n{message}"),
    )

    if "email" in notifier_types and (not email.host or not email.from_addr or not email.to_addr):
        errors.append("SMTP_HOST, SMTP_FROM, SMTP_TO are required when using email notifier")

    if "line" in notifier_types and not line.token:
        errors.append("LINE_NOTIFY_TOKEN is required when using line notifier")

    notify_retry_max_retries_raw = env.get("NOTIFY_RETRY_MAX_RETRIES", "2").strip()
    notify_retry_initial_delay_raw = env.get("NOTIFY_RETRY_INITIAL_DELAY_SECONDS", "60").strip()
    try:
        notify_retry_max_retries = int(notify_retry_max_retries_raw)
        if notify_retry_max_retries < 0:
            raise ValueError
    except ValueError:
        notify_retry_max_retries = 2
        errors.append("NOTIFY_RETRY_MAX_RETRIES must be an integer >= 0")

    try:
        notify_retry_initial_delay_seconds = int(notify_retry_initial_delay_raw)
        if notify_retry_initial_delay_seconds < 0:
            raise ValueError
    except ValueError:
        notify_retry_initial_delay_seconds = 60
        errors.append("NOTIFY_RETRY_INITIAL_DELAY_SECONDS must be an integer >= 0")

    gcp_project_id = env.get("GCP_PROJECT_ID", "").strip()
    firestore_database = env.get("FIRESTORE_DATABASE", "(default)").strip() or "(default)"
    firestore_collection_prefix = env.get("FIRESTORE_COLLECTION_PREFIX", "").strip()
    if state_backend == "firestore" and not gcp_project_id:
        errors.append("GCP_PROJECT_ID is required when STATE_BACKEND=firestore")

    if errors:
        raise ConfigValidationError(errors)

    return AppConfig(
        state_backend=state_backend,
        bangumi_id=env.get("TARGET_BANGUMI_ID", "").strip(),
        target_name=env.get("TARGET_NAME", "").strip(),
        data_dir=Path(env.get("DATA_DIR", "data")),
        notifier_types=notifier_types,
        gcp_project_id=gcp_project_id,
        firestore_database=firestore_database,
        firestore_collection_prefix=firestore_collection_prefix,
        notify_retry_max_retries=notify_retry_max_retries,
        notify_retry_initial_delay_seconds=notify_retry_initial_delay_seconds,
        email=email,
        line=line,
    )
