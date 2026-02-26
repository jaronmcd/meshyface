from typing import Optional


def is_sensitive_key(key: str, sensitive_field_names: set[str]) -> bool:
    key_l = key.lower()
    if key_l in sensitive_field_names:
        return True
    return key_l.endswith("_password") or key_l.endswith("_private_key")


def redact_secrets(
    value: object,
    sensitive_field_names: set[str],
    parent_key: Optional[str] = None,
) -> object:
    if parent_key and is_sensitive_key(parent_key, sensitive_field_names):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            key: redact_secrets(val, sensitive_field_names, key)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item, sensitive_field_names, parent_key) for item in value]
    return value
