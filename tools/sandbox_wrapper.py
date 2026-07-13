"""Per-webhook OS-sandbox wrapping for terminal subprocesses.

Sessions started by configured webhook routes get every terminal command
wrapped in an OS-level sandbox launcher (e.g. a Seatbelt profile script),
so filesystem/secret/Docker restrictions are mechanical rather than
prompt policy.

Configuration (config.yaml)::

    terminal:
      sandbox_wrappers:
        linear-crm-autowork: "~/.hermes/scripts/restricted_worker.sh"
        github-pr-review: "~/.hermes/scripts/restricted_worker.sh --allow-docker"

The key is the webhook route name; the value is the wrapper command
(shlex-split, argv[0] user-expanded) prepended to the shell argv.

Fail-closed: if a route is configured for sandboxing but the wrapper is
missing or unreadable, the command raises instead of silently running
unsandboxed.
"""

from __future__ import annotations

import logging
import os
import shlex

logger = logging.getLogger(__name__)


class SandboxWrapperError(RuntimeError):
    """Raised when a configured sandbox wrapper cannot be applied."""


def _current_webhook_route() -> str | None:
    """Return the webhook route that started this session, if any."""
    chat_id = ""
    try:
        from gateway.session_context import _UNSET, _VAR_MAP

        value = _VAR_MAP["HERMES_SESSION_CHAT_ID"].get()
        if value is not _UNSET and value:
            chat_id = str(value)
    except Exception:
        chat_id = ""
    if not chat_id:
        chat_id = os.environ.get("HERMES_SESSION_CHAT_ID", "")
    # Webhook sessions use chat ids of the form "webhook:<route>:<delivery>".
    if not chat_id.startswith("webhook:"):
        return None
    parts = chat_id.split(":", 2)
    return parts[1] if len(parts) >= 2 and parts[1] else None


def _configured_wrappers() -> dict:
    try:
        from hermes_cli.config import cfg_get, read_raw_config

        wrappers = cfg_get(read_raw_config(), "terminal", "sandbox_wrappers")
    except Exception:
        return {}
    return wrappers if isinstance(wrappers, dict) else {}


def sandbox_prefix() -> list[str]:
    """Return the argv prefix to sandbox the current session's commands.

    Empty list means the session is not subject to sandbox wrapping.
    """
    route = _current_webhook_route()
    if route is None:
        return []
    spec = _configured_wrappers().get(route)
    if not spec or not isinstance(spec, str):
        return []
    argv = shlex.split(spec)
    if not argv:
        return []
    argv[0] = os.path.expanduser(argv[0])
    if not os.path.isfile(argv[0]) or not os.access(argv[0], os.X_OK):
        # A configured-but-broken wrapper must never degrade to unsandboxed
        # execution.
        raise SandboxWrapperError(
            f"sandbox wrapper for webhook route {route!r} is missing or not "
            f"executable: {argv[0]}"
        )
    logger.debug("sandbox wrapper active for route %s: %s", route, argv)
    return argv
