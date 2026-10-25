import urllib.request
import urllib.error
import uuid

url = "http://127.0.0.1:8000/api/input/upload/folder"
boundary = uuid.uuid4().hex
long_path = "a/"*80 + "test.py"

body = b'--' + boundary.encode() + b'\r\n'
body += b'Content-Disposition: form-data; name="paths"\r\n\r\n'
body += long_path.encode() + b'\r\n'
body += b'--' + boundary.encode() + b'\r\n'
body += b'Content-Disposition: form-data; name="files"; filename="test.py"\r\n'
body += b'Content-Type: text/plain\r\n\r\n'
body += b'print("hi")\r\n'
body += b'--' + boundary.encode() + b'--\r\n'

req = urllib.request.Request(url, data=body, method='POST')
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

try:
    with urllib.request.urlopen(req) as resp:
        print("Status:", resp.status)
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print("Status:", e.code)
    print(e.read().decode())
