import os
os.environ['GROQ_API_KEY'] = 'gsk_FAKE_TEST_1234567890'
from backend.ai.explainer import AIExplainer, AIExplainerError

e = AIExplainer(provider='groq')
leaked = False
try:
    r = e.explain_issue({'rule_id':'B101','severity':'LOW','line':1,'file':'x.py','message':'t'})
    leaked = 'gsk_FAKE_TEST_1234567890' in str(r)
    print('returned explanation present:', bool(r.get('explanation')))
except AIExplainerError as ex:
    leaked = 'gsk_FAKE_TEST_1234567890' in str(ex)
    print('raised AIExplainerError:', str(ex))

print('key leaked:', leaked)
assert leaked is False, 'FAIL: key leaked'
print('TEST3 PASS (Rule 5 verified)')