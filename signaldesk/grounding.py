"""Optional Tavily public-vendor docs. Fixed queries, off by default, no ticket text."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from .budget import GuardError
from .providers import ProviderError
from .safeio import atomic_json, credential, digest, parse, post

# Domains AND paths are checked locally after search. Search snippets are untrusted.
SOURCES = {
    'RB-CLEAN': ('sg_logs TapeAlert log page cleaning flags', 'manpages.debian.org', '/bookworm/sg3-utils/'),
    'RB-MEDIA': ('sg_read_attr tape cartridge medium attributes', 'manpages.debian.org', '/bookworm/sg3-utils/'),
    'RB-HWFAULT': ('SCSI sense key hardware error additional sense codes', 'www.t10.org', '/lists/'),
    'RB-MOUNT': ('mtx medium changer load and status', 'manpages.debian.org', '/bookworm/mtx/'),
    'RB-INVENTORY': ('mtx medium changer inventory element status', 'manpages.debian.org', '/bookworm/mtx/'),
    'RB-LTFS': ('LTFS ltfsck index consistency rollback', 'github.com', '/LinearTapeFileSystem/'),
    'RB-PATH': ('lsscsi list SCSI devices generic names', 'manpages.debian.org', '/bookworm/lsscsi/'),
    'RB-WRITEPROT': ('mt magnetic tape status write protect', 'manpages.debian.org', '/bookworm/mt-st/')
}


def allowed_url(url, family):
    if not isinstance(url, str) or len(url) > 1000 or any(ord(c) < 33 or ord(c) > 126 for c in url):
        return False
    try:
        p = urlsplit(url)
        _, host, prefix = SOURCES[family]
        return (p.scheme == 'https' and p.hostname == host and p.netloc == host
                and p.path.startswith(prefix) and not p.username and not p.password
                and not p.query and not p.fragment and not p.port
                and '%' not in p.path and '..' not in p.path and '\\' not in p.path)
    except (ValueError, KeyError):
        return False


def validate_docs(docs):
    if not isinstance(docs, list) or len(docs) > 24:
        raise ValueError('Invalid public document list')
    seen = set()
    for d in docs:
        if (not isinstance(d, dict) or set(d) != {'id', 'family', 'title', 'url', 'excerpt', 'origin', 'retrieved_at'}
                or d['family'] not in SOURCES or d['origin'] not in {'tavily-live', 'injected-mock'}
                or d['title'] != SOURCES[d['family']][0] or not isinstance(d['excerpt'], str)
                or len(d['excerpt']) > 240 or len(d['excerpt'].split()) > 20
                or not allowed_url(d['url'], d['family'])
                or d['id'] != 'WEB-' + digest({'family': d['family'], 'url': d['url']})[:16]
                or d['id'] in seen or not isinstance(d['retrieved_at'], str)
                or len(d['retrieved_at']) > 40):
            raise ValueError('Invalid public document citation')
        datetime.fromisoformat(d['retrieved_at'])
        seen.add(d['id'])
    return docs


class PublicDocs:
    def __init__(self, budget, cache_dir, enabled=False, replay=False, transport=post):
        self.budget, self.directory = budget, Path(cache_dir)
        self.enabled, self.replay, self.transport = enabled, replay, transport
        self.origin = 'tavily-live' if transport is post else 'injected-mock'
        self.memory = {}

    def search(self, family):
        if not self.enabled:
            return []  # Do not even read TAVILY_API_KEY unless explicitly enabled.
        if family not in SOURCES:
            raise ProviderError('Unknown public documentation family')
        if family in self.memory:
            return self.memory[family]
        query, host, _ = SOURCES[family]
        payload = {'query': query, 'search_depth': 'basic', 'topic': 'general',
                   'max_results': 3, 'include_domains': [host], 'include_answer': False,
                   'include_raw_content': False, 'include_images': False, 'auto_parameters': False,
                   'include_usage': True}
        key = digest({'version': 1, 'origin': self.origin, 'payload': payload})
        path = self.directory / (key + '.json')
        if path.exists():
            try:
                record = parse(path.read_bytes())
                if record['key'] != key or record['sha256'] != digest(record['docs']):
                    raise ValueError('Cache mismatch')
                docs = validate_docs(record['docs'])
                if any(d['origin'] != self.origin or d['family'] != family for d in docs):
                    raise ValueError('Origin mismatch')
            except (ValueError, KeyError, TypeError, OSError, RecursionError):
                raise ProviderError('Public-doc cache failed validation') from None
        elif self.replay:
            raise ProviderError('Public-doc cache miss; replay makes no requests')
        else:
            token = 'local-fixture-only' if self.origin != 'tavily-live' else credential('TAVILY_API_KEY')
            self.budget.reserve_search()
            try:
                response = self.transport('https://api.tavily.com/search', payload, token)
                if type(response['usage']['credits']) is not int or response['usage']['credits'] != 1:
                    raise GuardError('Unexpected Tavily credits; stop all further requests')
                self.budget.search_credits_observed += 1
                rows = response['results']
                if not isinstance(rows, list) or len(rows) > 3:
                    raise ValueError('Invalid results')
                docs, seen = [], set()
                for row in rows:
                    url = row.get('url')
                    if not allowed_url(url, family) or url in seen:
                        continue
                    seen.add(url)
                    excerpt = ' '.join(str(row.get('content', '')).split()[:20])[:240]
                    docs.append({'id': 'WEB-' + digest({'family': family, 'url': url})[:16],
                                 'family': family, 'title': query, 'url': url, 'excerpt': excerpt,
                                 'origin': self.origin, 'retrieved_at': datetime.now(timezone.utc).isoformat()})
                validate_docs(docs)
            except GuardError:
                raise
            except Exception:
                raise ProviderError('Public documentation search failed; no response body logged') from None
            atomic_json(path, {'key': key, 'docs': docs, 'sha256': digest(docs)})
        self.memory[family] = docs
        return docs
