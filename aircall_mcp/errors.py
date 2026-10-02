"""Safe, typed failures that may be shown to MCP tool callers."""

from mcp.server.mcpserver.exceptions import ToolError


class AircallFailure(ToolError, RuntimeError):
    """Base class for anticipated Aircall failures with fixed safe descriptions."""


class MissingCredentialsError(AircallFailure):
    def __init__(self):
        super().__init__(
            "Aircall credentials not found. Set AIRCALL_API_ID and "
            "AIRCALL_API_TOKEN or run aircall-mcp-setup."
        )


class AuthorizationError(AircallFailure):
    def __init__(self):
        super().__init__(
            "Aircall access denied: the connected account lacks permission for this action "
            "(or the authorization expired; re-run aircall-mcp-setup if so)."
        )


class AuthenticationError(AircallFailure):
    def __init__(self):
        super().__init__(
            "Aircall authentication failed. Re-run aircall-mcp-setup to refresh the authorization."
        )


class VendorHTTPError(AircallFailure):
    def __init__(self, status_code: int, reason: str):
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"Aircall returned HTTP {status_code}: {reason}.")


class NotFoundError(AircallFailure):
    def __init__(self):
        super().__init__("The requested Aircall resource was not found.")


class RateLimitedError(AircallFailure):
    def __init__(self, retry_after: int | None):
        self.retry_after = retry_after
        hint = (
            f"Retry after about {retry_after} seconds."
            if retry_after is not None
            else "Retry later."
        )
        super().__init__(f"Aircall rate limit reached. {hint}")


class ArgumentShapeError(AircallFailure, ValueError):
    def __init__(self, argument: str, expected: str):
        self.argument = argument
        self.expected = expected
        super().__init__(f"Argument {argument} must be {expected}.")


class TransportError(AircallFailure):
    def __init__(self):
        super().__init__(
            "Aircall request outcome is unknown. Check whether the operation completed before retrying."
        )


class ReadTransportError(AircallFailure):
    def __init__(self):
        super().__init__(
            "Aircall read request did not complete. You may retry the read."
        )
