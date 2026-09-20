import requests, time

for attempt in range(10):
    try:
        r = requests.get("http://localhost:8000/health", timeout=3)
        data = r.json()
        print(f"✅ API UP — provider: {data.get('active_provider')} | cascade: {data.get('all_providers')}")
        break
    except Exception as e:
        print(f"  Attempt {attempt+1}: {e}")
        time.sleep(2)
else:
    print("❌ API failed to start in 20s")
