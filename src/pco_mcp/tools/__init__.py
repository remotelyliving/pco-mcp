"""Shared annotation constants for MCP tool registration."""

READ_ANNOTATIONS = {"readOnlyHint": True, "openWorldHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True, "confirmationHint": True}
DESTRUCTIVE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True, "confirmationHint": True}
