import urllib.request
import urllib.error
import uuid

url = "http://127.0.0.1:8000/api/input/upload/folder"
boundary = uuid.uuid4().hex
body = b''

for i in range(501):
    body += b'--' + boundary.encode() + b'\r\n'
    body += b'Content-Disposition: form-data; name="paths"\r\n\r\n'
    body += f'f{i}.py\r\n'.encode()
    body += b'--' + boundary.encode() + b'\r\n'
    body += f'Content-Disposition: form-data; name="files"; filename="f{i}.py"\r\n'.encode()
    body += b'Content-Type: text/plain\r\n\r\n'
    body += b'pass\r\n'
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
