from __future__ import annotations


class EgrepError(RuntimeError):
    """Base class for expected command failures."""

    exit_code = 1


class IndexNotFoundError(EgrepError):
    exit_code = 3


class ProviderConfigError(EgrepError):
    exit_code = 4


class ProviderAPIError(EgrepError):
    exit_code = 5


class IndexWriteError(EgrepError):
    exit_code = 6
