"""Shared boundaries for app-owned Frappe RPC APIs."""

TRANSPORT_METADATA_FIELDS = frozenset({"cmd"})


def without_transport_metadata(values):
    """Remove Frappe request routing keys before strict business validation."""
    return {key: value for key, value in values.items() if key not in TRANSPORT_METADATA_FIELDS}
