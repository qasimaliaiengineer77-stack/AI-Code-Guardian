import os, shutil
from unittest.mock import patch

from backend.input_handler.uploads import new_scan_id, scan_dir
from backend.orchestrator import runner as rmod
from backend.storage.scans import get_scan

def _mk_ws(sid, filename='bad.py', content='password = \"hunter2\"\nimport hashlib\nh = hashlib.md5(b\"x\").hexdigest()\n'):
    ws = scan_dir(sid)
    os.makedirs(ws, exist_ok=True)
    p = os.path.join(ws, filename)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    return ws

# ---------- TEST 1: normal scan ----------
rmod._reset_ai_circuit()
os.environ.pop('AI_PROVIDER', None)
os.environ.pop('GROQ_API_KEY', None)
os.environ.pop('GEMINI_API_KEY', None)
sid = new_scan_id()
_mk_ws(sid)
result = rmod.run_scan(sid, language='en', explain=True)
assert result['status'] == 'done', result['status']
assert result['total_issues'] >= 1, 'expected >=1 issue, got ' + str(result['total_issues'])
assert len(result['issues']) >= 1
for i in result['issues']:
    assert 'explanation' in i, 'missing explanation'
    assert 'code' not in i, 'code field leaked!'
    assert 'snippet' not in i, 'snippet field leaked!'
assert result['ai_status'] == 'disabled', result['ai_status']  # no key -> disabled
row = get_scan(sid)
assert row and row['status'] == 'done' and row['result'] is not None
print('TEST1 PASS')

# ---------- TEST 2: edge (invalid id + missing ws) ----------
try:
    rmod.run_scan('not-valid-id')
    raise SystemExit('FAIL: should have raised for bad id')
except rmod.ScanRunError as e:
    assert e.status == 400, e.status
sid2 = new_scan_id()
try:
    rmod.run_scan(sid2)
    raise SystemExit('FAIL: should have raised for missing ws')
except rmod.ScanRunError as e:
    assert e.status == 404, e.status
print('TEST2 PASS')

# ---------- TEST 3: AI fail -> fallback + circuit breaker ----------
os.environ['AI_PROVIDER'] = 'groq'
os.environ['GROQ_API_KEY'] = 'gsk_FAKE_TEST_1234567890'
rmod._reset_ai_circuit()

orig_explain = rmod.AIExplainer.explain_issues
def boom(self, issues, language='en'):
    if not self.available:
        return orig_explain(self, issues, language)
    raise __import__('backend.ai.explainer', fromlist=['AIExplainerError']).AIExplainerError('simulated auth failure')

sid3 = new_scan_id()
_mk_ws(sid3)
with patch.object(rmod.AIExplainer, 'explain_issues', boom):
    r3 = rmod.run_scan(sid3, language='en', explain=True)

assert r3['ai_status'] == 'unavailable', r3['ai_status']
assert r3['ai_message'] == 'AI explanation temporarily unavailable', r3['ai_message']
assert len(r3['issues']) >= 1
assert all(i.get('explanation') for i in r3['issues']), 'fallback explanation missing'
assert all(i.get('explanation_available') is False for i in r3['issues'])

# no key leak anywhere in result (Rule 5)
assert 'gsk_FAKE_TEST_1234567890' not in str(r3), 'KEY LEAK'

# circuit now open -> next scan is 'cooldown', explain_issues NOT called
sid4 = new_scan_id()
_mk_ws(sid4)
calls = {'n': 0}
def spy(self, issues, language='en'):
    calls['n'] += 1
    return orig_explain(self, issues, language)
with patch.object(rmod.AIExplainer, 'explain_issues', spy):
    r4 = rmod.run_scan(sid4, language='en', explain=True)
assert r4['ai_status'] == 'cooldown', r4['ai_status']
assert 'temporarily unavailable' in r4['ai_message']
# spy can be called by fallback provider='none' path; but base AIExplainer (available) must not be invoked
# so verify: circuit remains open
from backend.orchestrator.runner import _AI_CIRCUIT
assert _AI_CIRCUIT['failed_until'] is not None

# cleanup
rmod._reset_ai_circuit()
os.environ.pop('AI_PROVIDER', None)
os.environ.pop('GROQ_API_KEY', None)
print('TEST3 PASS')