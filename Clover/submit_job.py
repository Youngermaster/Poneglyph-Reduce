import base64, json, sys, time, os
import urllib.request

MASTER = os.getenv("MASTER", "http://localhost:8080")

def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get_text(url):
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()

if __name__ == "__main__":
    # Ejemplo WordCount
    map_b64 = b64("map.py")
    reduce_b64 = b64("reduce.py")
    input_text = "one fish two fish\nred fish blue fish\n" * 10

    job = {
        "job_id": "wordcount-001",
        "input_text": input_text,
        "split_size": 64,
        "reducers": 2,
        "format": "text",
        "map_script_b64": map_b64,
        "reduce_script_b64": reduce_b64
    }
    r = post(f"{MASTER}/api/jobs", job)
    print("Submitted:", r)

    while True:
        st = json.loads(get_text(f"{MASTER}/api/jobs/status?job_id=wordcount-001"))
        print("Status:", st)
        if st["state"] in ("SUCCEEDED","FAILED"):
            break
        time.sleep(1)

    if st["state"] == "SUCCEEDED":
        out = get_text(f"{MASTER}/api/jobs/result?job_id=wordcount-001")
        print("RESULT:\n", out)
