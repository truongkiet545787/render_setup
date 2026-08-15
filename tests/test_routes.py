import pytest
from app import models

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["project"] == "AI Nutrition AR Agent"

def test_detect_existing_food_apple(client):
    response = client.get("/detect?name=apple")
    assert response.status_code == 200
    data = response.json()
    assert data["product_found"] is True
    assert data["name"] == "apple"
    assert data["details"] is not None
    assert data["details"]["name"] == "apple"
    assert data["details"]["nutrition"]["calories"] == 52.0
    assert len(data["details"]["ingredients"]) > 0

def test_detect_existing_food_banana(client):
    response = client.get("/detect?name=banana")
    assert response.status_code == 200
    data = response.json()
    assert data["product_found"] is True
    assert data["name"] == "banana"
    assert data["details"]["nutrition"]["calories"] == 89.0

def test_detect_non_existent_fallback(client, monkeypatch):
    # Mock the search agent to raise an exception, simulating a search failure
    def mock_query_nutrition_for_food(name):
        raise Exception("Search agent failed")
    
    import app.search_agent
    monkeypatch.setattr(app.search_agent, "query_nutrition_for_food", mock_query_nutrition_for_food)

    response = client.get("/detect?name=dragonfruit")
    assert response.status_code == 200
    data = response.json()
    assert data["product_found"] is False
    assert data["details"] is None

def test_chat_creation_and_persistence(client, session):
    session_id = "test_pytest_session_456"
    
    # Message 1
    payload = {
        "session_id": session_id,
        "message": "Quả táo này ăn có mập không?",
        "product_name": "apple"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "reply" in data
    assert len(data["history"]) == 2
    assert data["history"][0]["role"] == "user"
    assert data["history"][0]["content"] == payload["message"]
    assert data["history"][1]["role"] == "assistant"

    # Verify directly in the test database
    db_messages = session.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.time_created.asc()).all()
    
    assert len(db_messages) == 2
    assert db_messages[0].role == "user"
    assert db_messages[1].role == "assistant"

    # Message 2 - checking conversation continuation
    payload2 = {
        "session_id": session_id,
        "message": "Còn bún bò huế thì sao?",
        "product_name": "bun_bo_hue"
    }
    response2 = client.post("/chat", json=payload2)
    assert response2.status_code == 200
    
    data2 = response2.json()
    assert len(data2["history"]) == 4 # 2 from previous + 2 new
    assert data2["history"][2]["role"] == "user"
    assert data2["history"][3]["role"] == "assistant"
