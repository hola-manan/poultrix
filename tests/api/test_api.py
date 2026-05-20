"""
Tests for API endpoints and thread safety
"""
import pytest
import threading
from fastapi.testclient import TestClient
from jeevn.api.app import app, AOI_STORE, AOI_STORE_LOCK


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_aoi_basic(client):
    """Test basic AOI creation"""
    payload = {
        "name": "Test AOI",
        "geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [0.0, 0.0],
                        [1.0, 0.0],
                        [1.0, 1.0],
                        [0.0, 1.0],
                        [0.0, 0.0]
                    ]]
                }
            }]
        },
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }
    
    response = client.post("/aoi", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "aoi_id" in data
    assert data["aoi_id"] is not None


def test_aoi_store_thread_safety():
    """Test that AOI_STORE access is thread-safe"""
    # Clear the store first
    with AOI_STORE_LOCK:
        AOI_STORE.clear()
    
    results = []
    errors = []
    
    def add_aoi(aoi_id):
        try:
            with AOI_STORE_LOCK:
                AOI_STORE[aoi_id] = {
                    "id": aoi_id,
                    "name": f"AOI {aoi_id}",
                    "status": "created"
                }
            results.append(aoi_id)
        except Exception as e:
            errors.append(str(e))
    
    # Create multiple threads that access AOI_STORE
    threads = []
    for i in range(10):
        thread = threading.Thread(target=add_aoi, args=(f"aoi_{i}",))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Verify no errors occurred
    assert len(errors) == 0, f"Thread safety errors: {errors}"
    
    # Verify all AOIs were added
    with AOI_STORE_LOCK:
        assert len(AOI_STORE) == 10
    
    # Clean up
    with AOI_STORE_LOCK:
        AOI_STORE.clear()


def test_get_nonexistent_aoi(client):
    """Test retrieving a non-existent AOI returns 404"""
    response = client.get("/aoi/nonexistent-id/report")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
