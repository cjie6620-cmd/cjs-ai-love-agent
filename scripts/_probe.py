import urllib.request
try:
    r = urllib.request.urlopen("http://127.0.0.1:8000/chat/conversations?user_id=demo-user", timeout=8)
    print("OK", r.status)
    print(r.read()[:500])
except Exception as e:
    print("ERR", type(e).__name__, e)
