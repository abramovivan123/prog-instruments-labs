"""Regular expressions for the ten fields in variant 1."""

import re


# Each IPv4 octet is an integer from 0 to 255 without leading zeros.
IPV4_OCTET = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"

# Patterns describe the synthetic data format specified by the assignment.
PATTERNS = {
    "email": re.compile(
        r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*"
        r"@(?:[A-Za-z0-9]+\.)+[A-Za-z]{2,}"
    ),
    "http_status_message": re.compile(
        r"[1-5][0-9]{2} [A-Za-z]+(?:[ -][A-Za-z]+)*"
    ),
    "snils": re.compile(r"[0-9]{11}"),
    "passport": re.compile(r"[0-9]{2} [0-9]{2} [0-9]{6}"),
    "ip_v4": re.compile(rf"(?:{IPV4_OCTET}\.){{3}}{IPV4_OCTET}"),
    "longitude": re.compile(
        r"-?(?:(?:[0-9]|[1-9][0-9]|1[0-7][0-9])(?:\.[0-9]+)?"
        r"|180(?:\.0+)?)"
    ),
    "hex_color": re.compile(r"#[0-9a-fA-F]{6}"),
    "isbn": re.compile(
        r"(?:[0-9]-[0-9]{5}-[0-9]{3}-[0-9X]"
        r"|[0-9]{3}-[0-9]-[0-9]{5}-[0-9]{3}-[0-9])"
    ),
    "locale_code": re.compile(r"[a-z]{2}(?:-[a-z]{2})?"),
    "time": re.compile(
        r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{6}"
    ),
}
