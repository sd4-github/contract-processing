"""Opt-in Sentry and Datadog setup for API and worker processes."""

import logging
import os

from . import core

logger = logging.getLogger(__name__)
_configured = False


def configure() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    if core.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=core.SENTRY_DSN,
                environment=core.SENTRY_ENVIRONMENT,
                release=core.SENTRY_RELEASE or None,
                traces_sample_rate=core.SENTRY_TRACES_SAMPLE_RATE,
                profiles_sample_rate=core.SENTRY_PROFILES_SAMPLE_RATE,
            )
        except ImportError:
            logger.warning("SENTRY_DSN is set but sentry-sdk is not installed")

    if core.DD_TRACE_ENABLED:
        try:
            from ddtrace import config, patch_all
            os.environ.setdefault("DD_SERVICE", core.DD_SERVICE)
            os.environ.setdefault("DD_ENV", core.DD_ENV)
            os.environ.setdefault("DD_VERSION", core.DD_VERSION)
            os.environ.setdefault("DD_AGENT_HOST", core.DD_AGENT_HOST)
            config.service = core.DD_SERVICE
            config.env = core.DD_ENV
            config.version = core.DD_VERSION
            config.logs_injection = core.DD_LOGS_INJECTION
            patch_all()
        except ImportError:
            logger.warning("DD_TRACE_ENABLED is set but ddtrace is not installed")
