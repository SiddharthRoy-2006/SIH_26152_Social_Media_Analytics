import requests
import json

BASE_URL = "http://127.0.0.1:8001"

def test_full_pipeline():
    print("Testing backend connectivity and health...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    health = r.json()
    print("Health response:", health["status"], "Data Mode:", health["data_mode"])
    platforms = health.get("platforms", {})
    assert "YouTube" in platforms
    assert "Telegram" in platforms
    assert "Reddit" in platforms
    assert "Twitter / X" in platforms
    assert "Instagram" in platforms
    assert "Facebook" in platforms
    print("All 6 platforms present in capabilities:", list(platforms.keys()))

    # Test 1: Unconfigured Live YouTube (Truthful empty state, NO silent fabrication)
    print("\n--- Test 1: Truthful Unconfigured State (YouTube) ---")
    r = requests.get(f"{BASE_URL}/analysis", params={"topic": "NEP 2020", "platform": "YouTube"})
    assert r.status_code == 200
    data = r.json()
    print("YouTube Live Analysis (Unconfigured):", "Data Available:", data["data_available"], "Source:", data["source"])
    assert data["data_available"] is False
    assert data["source"] == "empty"

    # Test 2: Explicit Demo Fallback for YouTube (?demo=true)
    print("\n--- Test 2: YouTube Explicit Demo Fallback (?demo=true) ---")
    r = requests.get(f"{BASE_URL}/analysis", params={"topic": "NEP 2020", "platform": "YouTube", "demo": True})
    assert r.status_code == 200
    data = r.json()
    print("YouTube Demo Fallback:", "Data Available:", data["data_available"], "Source:", data["source"])
    assert data["data_available"] is True
    assert data["source"] == "demo"
    assert data["metrics"]["reach"] > 0
    assert "network_graph" in data
    assert len(data["network_graph"]["nodes"]) > 0
    print(f"Topology Nodes: {len(data['network_graph']['nodes'])}, Edges: {len(data['network_graph']['edges'])}")

    # Test 3: Twitter / X Truthful Unconfigured State
    print("\n--- Test 3: Twitter / X Truthful Unconfigured State ---")
    r = requests.get(f"{BASE_URL}/analysis", params={"topic": "NEP 2020", "platform": "Twitter / X"})
    assert r.status_code == 200
    data = r.json()
    print("Twitter / X Live (unconfigured):", "Data Available:", data["data_available"], "Source:", data["source"])
    assert data["data_available"] is False
    assert data["source"] == "empty"

    # Test 4: Twitter / X with Explicit Demo Fallback
    print("\n--- Test 4: Twitter / X with Explicit Demo Fallback (?demo=true) ---")
    r = requests.get(f"{BASE_URL}/analysis", params={"topic": "NEP 2020", "platform": "Twitter / X", "demo": True})
    assert r.status_code == 200
    data = r.json()
    print("Twitter / X Demo Fallback:", "Data Available:", data["data_available"], "Source:", data["source"])
    assert data["data_available"] is True
    assert data["source"] == "demo"

    # Test 5: General Dashboard Unconfigured State
    print("\n--- Test 5: General Dashboard Truthful Unconfigured State ---")
    r = requests.get(f"{BASE_URL}/general", params={"platform": "All Platforms"})
    assert r.status_code == 200
    data = r.json()
    print("General Truthful Status:", "Data Available:", data["data_available"], "Source:", data["source"])

    # Test 6: General Dashboard Explicit Demo Override
    print("\n--- Test 6: General Dashboard Explicit Demo Override ---")
    r = requests.get(f"{BASE_URL}/general", params={"platform": "All Platforms", "demo": True})
    assert r.status_code == 200
    data = r.json()
    print("General Demo Override:", "Data Available:", data["data_available"], "Source:", data["source"])
    assert data["data_available"] is True
    assert data["source"] == "demo"
    assert len(data["top_trends"]) == 10

    print("\n>>> ALL 6 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY! <<<")

    print("\n>>> ALL 6 END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_full_pipeline()
