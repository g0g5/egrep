from __future__ import annotations


class WegrepError(RuntimeError):
    """Base class for expected command failures."""

    exit_code = 1


class IndexNotFoundError(WegrepError):
    exit_code = 3


class ProviderConfigError(WegrepError):
    exit_code = 4


class ProviderAPIError(WegrepError):
    exit_code = 5


class IndexWriteError(WegrepError):
    exit_code = 6
