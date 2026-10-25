import os
import sys
import requests

# Hardcoded secret (Gitleaks pakrega)
API_KEY = "gsk_1234567890abcdefghijklmnopqrstuvwxyz"

def run_code(user_input):
    # Security issue (Bandit pakrega)
    eval(user_input)
    
    # Requests without verify (Semgrep pakrega)
    requests.get("https://example.com", verify=False)
    
    # Unused variable (Pylint pakrega)
    unused_var = "hello"

def complex_function(a, b, c, d, e):
    # Lizard complexity pakrega
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return "Too complex"
    return "Simple"