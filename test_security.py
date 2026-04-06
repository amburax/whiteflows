import json
import httpx
import time

URL = "http://localhost:8001/submit-lead"

def test_submission(name, email, hp=""):
    payload = {
        "name": name,
        "email": email,
        "phone": "98765 43210",
        "type": "retail",
        "hp_website_url": hp
    }
    print(f"Testing submission for {name} (HP: '{hp}')...")
    try:
        resp = httpx.post(URL, json=payload, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # 1. Test Honeypot (Should say success but discard internally)
    test_submission("Bot User", "bot@evil.com", hp="http://evil.com")
    
    # 2. Test Real User (Success)
    test_submission("Real Client", "murtazajd53@gmail.com")
    
    # 3. Test Rate Limit (4/hr) - we already used 2 slots (Honeypot + Real)
    # Let's use 3 more to trigger 429
    test_submission("User 3", "user3@test.com")
    test_submission("User 4", "user4@test.com")
    test_submission("User 5 (Limit)", "user5@test.com")
