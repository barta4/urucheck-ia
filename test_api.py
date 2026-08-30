import urllib.request

try:
    response = urllib.request.urlopen("http://localhost:8080/api/company/config")
    print(response.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode("utf-8"))
except Exception as e:
    print(e)
