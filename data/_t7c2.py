import os
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app
from backend.ai.explainer import AIExplainerError
from backend.input_handler.uploads import new_scan_id, scan_dir
from backend.orchestrator import runner as rmod

client = TestClient(app)


def _mk_ws(sid, content='password = \"hunter2secret\"\n'):
    ws = scan_dir(sid)
    with open(os.path.join(ws, 'bad.py'), 'w', encoding='utf-8') as f:
        f.write(content)


# ---------- TEST 1: normal run + get + list ----------
sid = new_scan_id()
_mk_ws(sid)
r = client.post(f'/api/scans/{sid}/run')
assert r.status_code == 200, (r.status_code, r.text)
body = r.json()
assert body['status'] == 'done'
assert body['total_issues'] >= 1
assert isinstance(body['issues'], list) and body['issues']
for i in body['issues']:
    assert 'code' not in i and 'snippet' not in i
assert body['ai_status'] in ('ok', 'disabled', 'unavailable', 'cooldown')

r2 = client.get(f'/api/scans/{sid}')
assert r2.status_code == 200
assert r2.json()['scan_id'] == sid

r3 = client.get('/api/scans?limit=5')
assert r3.status_code == 200
assert any(s['scan_id'] == sid for s in r3.json()['scans'])
print('TEST1 PASS')

# ---------- TEST 2: edge cases ----------
r = client.post('/api/scans/not-a-valid-id/run')
assert r.status_code == 400, r.status_code

sid_empty = new_scan_id()  # no workspace created
r = client.post(f'/api/scans/{sid_empty}/run')
assert r.status_code == 404, r.status_code

r = client.get('/api/scans/nonexistent')
assert r.status_code == 404

r = client.delete('/api/scans/nonexistent')
assert r.status_code == 404

# bad language silently falls back
sid_lang = new_scan_id()
_mk_ws(sid_lang)
r = client.post(f'/api/scans/{sid_lang}/run?language=NOT_A_LANG')
assert r.status_code == 200
print('TEST2 PASS')

# ---------- TEST 3: Rule 5 (no key leak) + Rule 3 (no raw secret in response) ----------
os.environ['AI_PROVIDER'] = 'groq'
os.environ['GROQ_API_KEY'] = 'gsk_FAKE_TEST_1234567890'
rmod._reset_ai_circuit()

orig = rmod.AIExplainer.explain_issues
def boom(self, issues, language='en'):
    if not self.available:
        return orig(self, issues, language)
    raise AIExplainerError('simulated')

sid3 = new_scan_id()
_mk_ws(sid3)
with patch.object(rmod.AIExplainer, 'explain_issues', boom):
    r = client.post(f'/api/scans/{sid3}/run')

assert r.status_code == 200, r.text
body = r.json()
assert body['ai_status'] == 'unavailable'
assert body['ai_message'] == 'AI explanation temporarily unavailable'
raw = r.text
assert 'gsk_FAKE_TEST_1234567890' not in raw, 'KEY LEAK'
for i in body['issues']:
    assert 'hunter2secret' not in (i.get('message') or ''), 'raw secret in message'
    assert 'code' not in i

# circuit now open -> second run should be cooldown and NOT call provider again
call_count = {'n': 0}
def spy(self, issues, language='en'):
    if self.available:
        call_count['n'] += 1
    return orig(self, issues, language)

sid4 = new_scan_id()
_mk_ws(sid4)
with patch.object(rmod.AIExplainer, 'explain_issues', spy):
    r = client.post(f'/api/scans/{sid4}/run')
assert r.status_code == 200
body4 = r.json()
assert body4['ai_status'] == 'cooldown'
assert 'temporarily unavailable' in body4['ai_message']
assert call_count['n'] == 0, 'retry control violated'

rmod._reset_ai_circuit()
os.environ.pop('AI_PROVIDER', None)
os.environ.pop('GROQ_API_KEY', None)
print('TEST3 PASS')