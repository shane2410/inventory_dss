"""Compatibility shim for Python versions that no longer ship ``cgi``.

Django 3.2 still imports ``cgi.parse_header`` during request parsing. Python
3.14 removed the stdlib module, so we provide the small subset this project
needs.
"""


def parse_header(line):
    """Parse a MIME-style header into a value and parameter dictionary."""
    if not line:
        return "", {}

    parts = []
    current = []
    in_quotes = False
    escape_next = False

    for character in line:
        if escape_next:
            current.append(character)
            escape_next = False
            continue
        if character == "\\" and in_quotes:
            current.append(character)
            escape_next = True
            continue
        if character == '"':
            in_quotes = not in_quotes
            current.append(character)
            continue
        if character == ";" and not in_quotes:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(character)

    parts.append("".join(current).strip())

    value = parts[0]
    params = {}
    for raw_param in parts[1:]:
        if not raw_param:
            continue
        if "=" in raw_param:
            key, raw_value = raw_param.split("=", 1)
            key = key.strip().lower()
            raw_value = raw_value.strip()
            if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == '"':
                raw_value = raw_value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
            params[key] = raw_value
        else:
            params[raw_param.strip().lower()] = ""

    return value, params