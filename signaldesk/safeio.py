"""Bounded JSON, atomic artifacts, credential-safe HTTP with no proxies/redirects."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.request
from .providers import NoRedirect, ProviderError

MAX_BYTES = 131072


def pack(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(pack(value)).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def parse(raw, max_bytes=MAX_BYTES):
    if not isinstance(raw, (bytes, str)) or len(raw) > max_bytes:
        raise ValueError('Invalid JSON size')
    def invalid_constant(value):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def atomic_json(path, value, public=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = pack(value) + b'\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.signaldesk-', delete=False) as f:
            temporary = Path(f.name)
            os.fchmod(f.fileno(), 0o644 if public else 0o600)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def post(url, payload, credential):
    request = urllib.request.Request(url, data=pack(payload), method='POST',
        headers={'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=45) as response:
            raw = response.read(MAX_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError):
        raise ProviderError('Request failed; no retry, body or credential logged') from None
    try:
        return parse(raw)
    except (ValueError, TypeError, RecursionError):
        raise ProviderError('Response is oversized or invalid JSON') from None


def credential(name):
    value = os.environ.get(name, '')
    if not value or len(value) > 8192 or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in value):
        raise ProviderError(name + ' is missing or malformed; use the authorized broker')
    return value
