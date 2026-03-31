"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockingRecommendations:
    """Test suite for GET /api/restocking/recommendations."""

    def test_get_recommendations_default_budget(self, client):
        """Test getting recommendations with default budget."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert "budget" in data
        assert "total_allocated" in data
        assert "remaining_budget" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert len(data["recommendations"]) > 0

    def test_recommendation_structure(self, client):
        """Test that each recommendation has required fields."""
        response = client.get("/api/restocking/recommendations?budget=50000")
        data = response.json()

        for rec in data["recommendations"]:
            assert "item_sku" in rec
            assert "item_name" in rec
            assert "trend" in rec
            assert "recommended_quantity" in rec
            assert "unit_cost" in rec
            assert "line_cost" in rec
            assert "fits_budget" in rec
            assert isinstance(rec["recommended_quantity"], int)
            assert isinstance(rec["unit_cost"], (int, float))
            assert isinstance(rec["fits_budget"], bool)

    def test_greedy_priority_sort(self, client):
        """Test that increasing trend items are prioritized first."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        recs = data["recommendations"]
        trend_order = {"increasing": 0, "stable": 1, "decreasing": 2}
        ranks = [trend_order[r["trend"]] for r in recs]
        assert ranks == sorted(ranks), "Recommendations must be sorted by trend priority"

    def test_budget_allocation_math(self, client):
        """Test that allocated + remaining equals budget."""
        budget = 20000.0
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        data = response.json()

        assert abs(data["total_allocated"] + data["remaining_budget"] - budget) < 0.01

    def test_fits_budget_cutoff(self, client):
        """Test that items marked fits_budget actually fit cumulatively."""
        response = client.get("/api/restocking/recommendations?budget=15000")
        data = response.json()

        fitting_cost = sum(r["line_cost"] for r in data["recommendations"] if r["fits_budget"])
        assert fitting_cost <= data["budget"]
        assert abs(fitting_cost - data["total_allocated"]) < 0.01

    def test_zero_budget_nothing_fits(self, client):
        """Test that with zero budget no items fit."""
        response = client.get("/api/restocking/recommendations?budget=0")
        data = response.json()

        for rec in data["recommendations"]:
            assert rec["fits_budget"] is False
        assert data["total_allocated"] == 0

    def test_line_cost_calculation(self, client):
        """Test that line_cost equals quantity times unit_cost."""
        response = client.get("/api/restocking/recommendations?budget=50000")
        data = response.json()

        for rec in data["recommendations"]:
            expected = rec["recommended_quantity"] * rec["unit_cost"]
            assert abs(rec["line_cost"] - expected) < 0.01


class TestRestockingOrders:
    """Test suite for POST/GET /api/restocking/orders."""

    def test_create_restocking_order(self, client):
        """Test submitting a restocking order."""
        payload = {
            "items": [
                {"item_sku": "WDG-001", "item_name": "Industrial Widget Type A", "quantity": 100, "unit_cost": 12.5},
                {"item_sku": "GSK-203", "item_name": "High-Temperature Gasket", "quantity": 200, "unit_cost": 8.75}
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 200

        order = response.json()
        assert order["order_number"].startswith("RST-")
        assert order["status"] == "Submitted"
        assert len(order["items"]) == 2
        assert abs(order["total_value"] - (100 * 12.5 + 200 * 8.75)) < 0.01

    def test_lead_time_assigned_per_item(self, client):
        """Test that each item gets a lead time between 7 and 21 days."""
        payload = {
            "items": [
                {"item_sku": "FLT-405", "item_name": "Oil Filter Cartridge", "quantity": 500, "unit_cost": 6.25}
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        order = response.json()

        for item in order["items"]:
            assert "lead_time_days" in item
            assert 7 <= item["lead_time_days"] <= 21

    def test_expected_delivery_matches_max_lead(self, client):
        """Test that expected_delivery reflects the longest lead time."""
        from datetime import datetime

        payload = {
            "items": [
                {"item_sku": "VLV-506", "item_name": "Pressure Relief Valve", "quantity": 50, "unit_cost": 67.50}
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        order = response.json()

        order_dt = datetime.fromisoformat(order["order_date"])
        delivery_dt = datetime.fromisoformat(order["expected_delivery"])
        delta_days = (delivery_dt - order_dt).days

        max_lead = max(item["lead_time_days"] for item in order["items"])
        assert delta_days == max_lead

    def test_create_order_empty_items_rejected(self, client):
        """Test that empty item list returns 400."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_get_restocking_orders_returns_submitted(self, client):
        """Test that GET returns previously submitted orders."""
        payload = {
            "items": [
                {"item_sku": "CTL-330", "item_name": "Logic Controller Board", "quantity": 10, "unit_cost": 125.0}
            ]
        }
        client.post("/api/restocking/orders", json=payload)

        response = client.get("/api/restocking/orders")
        assert response.status_code == 200

        orders = response.json()
        assert isinstance(orders, list)
        assert len(orders) > 0
        assert any(
            any(it["item_sku"] == "CTL-330" for it in o["items"])
            for o in orders
        )
