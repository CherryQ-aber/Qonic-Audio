"""Central QML startup-mode resolution.

The QML entrypoint deliberately keeps runtime intent separate from individual
feature checks.  A mode resolves once at startup, produces a fixed
``CapabilityGate``, and all ViewModels continue to use that gate as their
non-destructive safety boundary.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ui_next.bridge.capabilities import (
    DEFAULT_USER_CAPABILITIES,
    CapabilityGate,
)


DEFAULT_USER_MODE = "default_user"
PREVIEW_MODE = "preview"
TEST_MODE = "test"


class RuntimeModeParseError(ValueError):
    """Raised before QApplication starts when a QML-specific flag is invalid."""


@dataclass(frozen=True)
class RuntimeModeConfig:
    """Resolved startup contract shared by the QML entrypoint and tests."""

    mode: str
    requested_capabilities: object
    app_arguments: tuple[str, ...]
    smoke_test: bool = False
    open_settings: bool = False
    requested_module: str = ""
    legacy_user_trial_requested: bool = False
    legacy_capabilities_requested: bool = False
    legacy_live_requested: bool = False

    @property
    def is_preview(self) -> bool:
        return self.mode in {PREVIEW_MODE, TEST_MODE}

    @property
    def is_test(self) -> bool:
        return self.mode == TEST_MODE

    def create_capability_gate(self) -> CapabilityGate:
        return CapabilityGate(
            self.requested_capabilities,
            runtime_mode=self.mode,
            legacy_live_requested=self.legacy_live_requested,
            legacy_user_trial_requested=self.legacy_user_trial_requested,
        )


def resolve_runtime_mode(
    argv: Sequence[str] | None = None,
    environment: Mapping[str, str] | None = None,
) -> RuntimeModeConfig:
    """Resolve all QML-specific mode inputs before any bridge is constructed.

    Explicit command-line preview/test flags always win over compatibility
    environment variables.  The old capability environment remains useful for
    narrow development checks, while a plain launch now receives the complete
    user-safe capability profile.
    """

    raw_args = list(os.sys.argv if argv is None else argv)
    env = os.environ if environment is None else environment
    has_program_name = bool(raw_args and not str(raw_args[0]).startswith("-"))
    qml_args = raw_args[1:] if has_program_name else raw_args

    preview_requested = False
    smoke_test = False
    open_settings = False
    requested_module = ""
    app_arguments = [raw_args[0]] if has_program_name else []

    for arg in qml_args:
        if arg == "--preview":
            preview_requested = True
        elif arg == "--qml-smoke-test":
            smoke_test = True
        elif arg == "--qml-open-settings":
            open_settings = True
        elif arg.startswith("--qml-open-module="):
            requested_module = arg.split("=", 1)[1].strip()
            if not requested_module:
                raise RuntimeModeParseError("--qml-open-module 需要提供模块名称。")
        elif arg.startswith("--"):
            raise RuntimeModeParseError(f"不支持的 QML 启动参数：{arg}")
        else:
            # Preserve standard Qt arguments such as ``-platform offscreen``.
            app_arguments.append(arg)

    legacy_user_trial_requested = env.get("CHERRYQ_QML_USER_TEST") == "1"
    legacy_capabilities = str(env.get("CHERRYQ_QML_CAPS") or "").strip()
    legacy_live_requested = env.get("CHERRYQ_QML_LIVE") == "1"

    if smoke_test:
        mode = TEST_MODE
        requested_capabilities: object = ()
    elif preview_requested:
        mode = PREVIEW_MODE
        requested_capabilities = ()
    elif legacy_user_trial_requested:
        # Keep the former trial entry deterministic even if a shell still has
        # a narrow CHERRYQ_QML_CAPS value from an older development session.
        mode = DEFAULT_USER_MODE
        requested_capabilities = DEFAULT_USER_CAPABILITIES
    elif legacy_capabilities:
        # Keep focused development and older automation invocations working.
        mode = DEFAULT_USER_MODE
        requested_capabilities = legacy_capabilities
    else:
        # A plain launch receives the same profile as the legacy user-test
        # compatibility entry, without exposing test terminology in the UI.
        mode = DEFAULT_USER_MODE
        requested_capabilities = DEFAULT_USER_CAPABILITIES

    return RuntimeModeConfig(
        mode=mode,
        requested_capabilities=requested_capabilities,
        app_arguments=tuple(app_arguments),
        smoke_test=smoke_test,
        open_settings=open_settings,
        requested_module=requested_module,
        legacy_user_trial_requested=legacy_user_trial_requested,
        legacy_capabilities_requested=bool(legacy_capabilities),
        legacy_live_requested=legacy_live_requested,
    )
