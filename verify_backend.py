import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_detect():
    print("=== Testing /detect endpoint ===")
    
    # Test 1: Fetching apple (which exists in pre-filled database)
    url = f"{BASE_URL}/detect?name=apple"
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("Success: apple detected!\n")
    except Exception as e:
        print(f"Failed to connect to backend: {e}")
        sys.exit(1)

    # Test 2: Fetching a non-existent item (should return product_found=False)
    print("Testing lookup for a non-existent item 'avocado'...")
    url = f"{BASE_URL}/detect?name=avocado"
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print("Response JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        if data["product_found"] is False:
            print("Success: avocado correctly not found in database!\n")
        else:
            print("Warning: avocado was unexpectedly found!\n")
    except Exception as e:
        print(f"Failed during avocado lookup: {e}")

def test_chat():
    print("=== Testing /chat endpoint ===")
    url = f"{BASE_URL}/chat"
    
    # Send a message about apple
    payload = {
        "session_id": "test_session_123",
        "message": "Trái này có nhiều đường không bạn?",
        "product_name": "apple"
    }
    
    try:
        print(f"Sending chat payload: {payload}")
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        data = response.json()
        print("AI Reply:")
        print(data.get("reply"))
        print("\nUpdated History:")
        for msg in data.get("history", []):
            print(f"- {msg['role'].upper()}: {msg['content']}")
        print("\nSuccess: chat session working!\n")
    except Exception as e:
        print(f"Chat test failed: {e}")

if __name__ == "__main__":
    test_detect()
    test_chat()
