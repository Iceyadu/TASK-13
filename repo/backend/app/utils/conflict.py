from fastapi import HTTPException, status


def raise_conflict(
    your_version: int,
    server_version: int,
    your_data: dict,
    server_data: dict,
    changed_fields: list[str],
):
    """Raise a 409 Conflict with side-by-side data for client resolution."""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "conflict",
            "message": "Record has been modified by another user",
            "your_version": your_version,
            "server_version": server_version,
            "your_data": your_data,
            "server_data": server_data,
            "changed_fields": changed_fields,
        },
    )


def detect_changed_fields(your_data: dict, server_data: dict) -> list[str]:
    """Compare two dicts and return a list of keys that differ."""
    changed = []
    all_keys = set(your_data.keys()) | set(server_data.keys())
    for key in all_keys:
        if your_data.get(key) != server_data.get(key):
            changed.append(key)
    return sorted(changed)
