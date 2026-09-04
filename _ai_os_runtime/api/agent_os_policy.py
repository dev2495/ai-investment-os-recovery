"""Explicit request authorization. Shared Office never inherits private scope.

Principals are supplied by the authenticated host adapter, never request JSON.
This module has no credentials, permission promotion or broker capability.
"""
from dataclasses import dataclass
import re

try:
    from .agent_runtime import literal
    from .agent_runtime_api import RuntimeRequestError
except ImportError:
    from agent_runtime import literal
    from agent_runtime_api import RuntimeRequestError


@dataclass(frozen=True)
class Principal:
    user_id: str = 'local_operator'
    scope: str = 'internal'
    books: tuple[int, ...] = ()
    clients: tuple[int, ...] = ()
    actions: tuple[str, ...] = ('read', 'message', 'plan', 'control', 'handoff', 'routine_test', 'doctor')
    agent_id: int | None = None

    def __post_init__(self):
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', self.user_id) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', self.scope):
            raise ValueError('Invalid server-side principal')
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in (*self.books, *self.clients)):
            raise ValueError('Invalid book/client grant')

    def require(self, action: str):
        if action not in self.actions:
            raise RuntimeRequestError('This action is not authorized for this workspace.', 403)

    def clause(self, alias: str = '') -> str:
        if not re.fullmatch(r'[a-z_]*', alias):
            raise ValueError('Internal SQL alias required')
        p = alias + '.' if alias else ''
        books = ','.join(map(str, self.books)) or 'NULL'
        clients = ','.join(map(str, self.clients)) or 'NULL'
        return (f"{p}runtime_scope={literal(self.scope)} AND ({p}book_id IS NULL OR {p}book_id IN ({books})) "
                f"AND ({p}client_id IS NULL OR {p}client_id IN ({clients}))")

    def check_scope(self, row: dict):
        if (row.get('runtime_scope', 'internal') != self.scope or
            row.get('book_id') is not None and row['book_id'] not in self.books or
            row.get('client_id') is not None and row['client_id'] not in self.clients):
            raise RuntimeRequestError('Record not found in the authorized workspace.', 404)


_SENSITIVE = re.compile(r'(?i)(?:bearer\s+\S+|(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*\S+|-----BEGIN .*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{12,})')


def safe_text(value, limit=4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise RuntimeRequestError(f'Text must contain 1–{limit} characters.')
    if _SENSITIVE.search(value):
        raise RuntimeRequestError('Credential-like content is not accepted. Keep secrets in the existing local credential store.')
    return value.strip()


def request_key(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_.:-]{8,120}', value):
        raise RuntimeRequestError('A stable idempotency key (8–120 safe characters) is required.')
    return value


def evidence_refs(value) -> list[dict]:
    if not isinstance(value, list) or len(value) > 50:
        raise RuntimeRequestError('Provide at most 50 stored evidence references.')
    allowed = {'table', 'id', 'locator', 'content_hash'}
    result = []
    for ref in value:
        if not isinstance(ref, dict) or set(ref)-allowed or not re.fullmatch(r'(research|knowledge|core|agent)\.[a-z_]+', str(ref.get('table', ''))):
            raise RuntimeRequestError('Evidence must reference a stored record and locator, not arbitrary content.')
        if isinstance(ref.get('id'), bool) or not str(ref.get('id', '')).isdigit() or int(ref['id']) < 1:
            raise RuntimeRequestError('Evidence record ID is required.')
        item = {'table': ref['table'], 'id': int(ref['id'])}
        if 'locator' in ref:
            item['locator'] = safe_text(ref['locator'], 240)
        if 'content_hash' in ref:
            if not re.fullmatch(r'[a-f0-9]{64}', str(ref['content_hash'])):
                raise RuntimeRequestError('Invalid evidence content hash.')
            item['content_hash'] = ref['content_hash']
        result.append(item)
    return result
