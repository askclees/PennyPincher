"""Parses `nmcli -t -e yes -f ... device wifi list` output. Pure functions, no subprocess/nmcli
dependency, so this is unit-testable without a real WiFi adapter.

nmcli's terse mode (`-t`) separates fields with `:`, and by default (`-e yes`, the default even
if omitted) escapes literal `:` and `\\` inside field values with a `\\` prefix. This matters
because BSSIDs (`AA:BB:CC:DD:EE:FF`) contain colons — a naive `line.split(':')` would shatter one
BSSID into six pieces. `split_terse_line` handles this correctly with a single left-to-right scan
rather than a regex lookbehind, which would mis-handle an escaped-backslash immediately followed
by a real delimiter (`\\\\:` — escaped backslash then a real separator).
"""

# Confirmed against this machine's real `nmcli -f bogus device wifi list` error output, which
# lists every valid field name for `device wifi list`.
FIELDS = ("SSID", "BSSID", "SIGNAL", "CHAN", "FREQ", "SECURITY", "IN-USE")


def split_terse_line(line):
    """Splits one line of nmcli terse output into its raw (still-escaped-content, but
    unescaped-as-in-`\\:`-and-`\\\\`-resolved) field values."""
    fields = []
    current = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n:
            current.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            fields.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    fields.append("".join(current))
    return fields


def parse_wifi_list_output(output, fields=FIELDS):
    """Parses the full stdout of an `nmcli -t -f <fields> device wifi list` call into a list of
    {field_name: value} dicts, one per network line."""
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        values = split_terse_line(line)
        rows.append(dict(zip(fields, values)))
    return rows


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_network(row):
    """Converts one raw nmcli field dict (as produced by parse_wifi_list_output) into
    PennyPincher's network record shape."""
    return {
        "ssid": row.get("SSID") or None,
        "bssid": row.get("BSSID") or None,
        "signal": _to_int(row.get("SIGNAL")),
        "channel": _to_int(row.get("CHAN")),
        "frequency": row.get("FREQ") or None,
        "security": row.get("SECURITY") or None,
        "in_use": row.get("IN-USE") in ("*", "yes", "true", "Yes", "True"),
    }
