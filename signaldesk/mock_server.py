"""Local HTTP acceptance double. Never evidence of a vendor call or model accuracy."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from .core import validate_selection
from .safeio import pack


def mock_draft(context):
    case, books = context['incident'], context['runbooks']
    # A deterministic test double, deliberately not an LLM or expected-label lookup.
    for rb in books:
        ids = [e['id'] for e in case.get('evidence', []) if e.get('metric') == rb['metric']]
        try:
            accepted, _ = validate_selection({'runbook_id': rb['id'], 'evidence_ids': ids}, case, books)
        except ValueError:
            continue
        if accepted:
            rb, ids = accepted
            return {'runbook_id': rb['id'], 'evidence_ids': ids, 'hypothesis': rb['title'],
                    'steps': [{'source': rb['id'], 'step': i+1, 'text': s} for i, s in enumerate(rb['steps'])],
                    'web_citations': []}
    return {'runbook_id': None, 'evidence_ids': [], 'hypothesis': None, 'steps': [], 'web_citations': []}


@contextmanager
def mock_server():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/v1/chat/completions' or self.headers.get('Authorization') != 'Bearer local-fixture-only':
                self.send_error(403)
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2_000_000:
                self.send_error(413)
                return
            try:
                payload = json.loads(self.rfile.read(size))
                calls.append(payload)
                content = payload['messages'][-1]['content']
                context = json.loads(content if isinstance(content, str) else content[0]['text'])
                # Vision transport is exercised; the mock never pretends to read pixels.
                if context.get('input_mode') == 'bundled-dashboard-screenshot':
                    from .core import case_by_id
                    from .live import public_case
                    context['incident'] = public_case(case_by_id('clean-demo'))
                draft = mock_draft(context)
                prompt = min(len(pack(context)), 8000)
                completion = min(600, payload['max_tokens'])
                data = pack({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(draft)}}],
                             'usage': {'prompt_tokens': prompt, 'completion_tokens': completion,
                                       'total_tokens': prompt+completion}})
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (ValueError, KeyError, TypeError):
                self.send_error(400)
        def log_message(self, *args):
            pass  # No headers, payloads, credentials or server exceptions in logs.
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%d/v1/chat/completions' % server.server_port, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
