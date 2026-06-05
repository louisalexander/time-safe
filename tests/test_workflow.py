from datetime import datetime, timedelta, timezone

from timesafe.vault.secret import Secret
from timesafe.vault.workflow import SEND_SECRET_SCRIPT, build_unlock_workflow_yaml


def _secret(email="a@b.co"):
    return Secret.create(
        "My Secret", datetime.now(timezone.utc) + timedelta(days=30), 999, "chain", email
    )


def test_yaml_is_dispatch_only_and_embeds_secret_fields():
    s = _secret()
    y = build_unlock_workflow_yaml(s)
    assert "workflow_dispatch" in y
    assert "schedule:" not in y
    assert "cron:" not in y
    assert s.id in y
    assert "My Secret" in y
    assert "a@b.co" in y
    assert "vault/scripts/send_secret.py" in y
    assert "tle" in y


def test_send_script_parses_and_uses_tlock_oauth_gmail():
    compile(SEND_SECRET_SCRIPT, "send_secret.py", "exec")  # must be valid Python
    assert "oauth2.googleapis.com/token" in SEND_SECRET_SCRIPT
    assert "messages/send" in SEND_SECRET_SCRIPT
    assert "too early" in SEND_SECRET_SCRIPT
    assert "/issues" in SEND_SECRET_SCRIPT
    assert "smtplib" not in SEND_SECRET_SCRIPT
