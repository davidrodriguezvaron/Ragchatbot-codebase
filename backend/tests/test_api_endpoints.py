"""Tests for FastAPI endpoint request/response handling

The real app.py mounts static files from ``../frontend`` and initialises
RAGSystem at module level, both of which break in CI environments.  Instead
of importing app.py, we use the ``api_client`` fixture from conftest.py which
spins up an inline test app with the identical route logic but no static-file
mount and a mocked RAGSystem.
"""

import pytest
from unittest.mock import patch


# ============================================================================
# POST /api/query — happy path
# ============================================================================

class TestQueryEndpointSuccess:
    """Successful /api/query request/response scenarios"""

    def test_returns_200(self, api_client):
        """POST /api/query with a valid body returns HTTP 200"""
        response = api_client.post("/api/query", json={"query": "What is MCP?"})
        assert response.status_code == 200

    def test_response_contains_answer(self, api_client):
        """Response body includes an ``answer`` field with non-empty text"""
        response = api_client.post("/api/query", json={"query": "What is MCP?"})
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_response_contains_sources(self, api_client):
        """Response body includes a ``sources`` list"""
        response = api_client.post("/api/query", json={"query": "What is MCP?"})
        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_source_has_text_and_link(self, api_client):
        """Each source entry exposes ``text`` and ``link`` fields"""
        response = api_client.post("/api/query", json={"query": "What is MCP?"})
        sources = response.json()["sources"]
        assert len(sources) >= 1
        for source in sources:
            assert "text" in source
            assert "link" in source

    def test_response_contains_session_id(self, api_client):
        """Response body includes a ``session_id`` string"""
        response = api_client.post("/api/query", json={"query": "What is MCP?"})
        data = response.json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0

    def test_session_id_is_generated_when_absent(self, api_client, mock_rag_system):
        """When no session_id is provided, one is created via session_manager"""
        api_client.post("/api/query", json={"query": "Hello"})
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_provided_session_id_is_forwarded(self, api_client, mock_rag_system):
        """When a session_id is supplied it is passed directly to rag_system.query()"""
        api_client.post(
            "/api/query",
            json={"query": "Follow-up", "session_id": "existing-session"},
        )
        mock_rag_system.session_manager.create_session.assert_not_called()
        call_args = mock_rag_system.query.call_args
        assert call_args[0][1] == "existing-session"

    def test_query_text_forwarded_to_rag_system(self, api_client, mock_rag_system):
        """The query string is passed unchanged to rag_system.query()"""
        api_client.post("/api/query", json={"query": "Explain RAG"})
        call_args = mock_rag_system.query.call_args
        assert call_args[0][0] == "Explain RAG"

    def test_session_id_echoed_back(self, api_client, mock_rag_system):
        """The session_id in the response matches the one used for the query"""
        mock_rag_system.session_manager.create_session.return_value = "fresh-id-42"
        response = api_client.post("/api/query", json={"query": "Hi"})
        assert response.json()["session_id"] == "fresh-id-42"


# ============================================================================
# POST /api/query — error handling
# ============================================================================

class TestQueryEndpointErrors:
    """Error conditions for /api/query"""

    def test_missing_query_field_returns_422(self, api_client):
        """Omitting the required ``query`` field returns HTTP 422 Unprocessable Entity"""
        response = api_client.post("/api/query", json={"session_id": "abc"})
        assert response.status_code == 422

    def test_empty_body_returns_422(self, api_client):
        """An empty JSON body returns HTTP 422 Unprocessable Entity"""
        response = api_client.post("/api/query", json={})
        assert response.status_code == 422

    def test_rag_system_exception_returns_500(self, api_client, mock_rag_system):
        """When rag_system.query() raises, the endpoint returns HTTP 500"""
        mock_rag_system.query.side_effect = RuntimeError("ChromaDB unavailable")
        response = api_client.post("/api/query", json={"query": "Anything"})
        assert response.status_code == 500

    def test_500_response_contains_detail(self, api_client, mock_rag_system):
        """The 500 response body includes a ``detail`` field with the error message"""
        mock_rag_system.query.side_effect = RuntimeError("Something went wrong")
        response = api_client.post("/api/query", json={"query": "Anything"})
        assert "detail" in response.json()
        assert "Something went wrong" in response.json()["detail"]


# ============================================================================
# GET /api/courses — happy path
# ============================================================================

class TestCoursesEndpointSuccess:
    """Successful /api/courses request/response scenarios"""

    def test_returns_200(self, api_client):
        """GET /api/courses returns HTTP 200"""
        response = api_client.get("/api/courses")
        assert response.status_code == 200

    def test_response_contains_total_courses(self, api_client):
        """Response body contains ``total_courses`` as an integer"""
        response = api_client.get("/api/courses")
        data = response.json()
        assert "total_courses" in data
        assert isinstance(data["total_courses"], int)

    def test_response_contains_course_titles(self, api_client):
        """Response body contains ``course_titles`` as a list of strings"""
        response = api_client.get("/api/courses")
        data = response.json()
        assert "course_titles" in data
        assert isinstance(data["course_titles"], list)

    def test_total_courses_matches_titles_length(self, api_client):
        """``total_courses`` equals the length of ``course_titles``"""
        response = api_client.get("/api/courses")
        data = response.json()
        assert data["total_courses"] == len(data["course_titles"])

    def test_course_titles_match_mock(self, api_client):
        """Returned titles match what mock_rag_system.get_course_analytics() provides"""
        response = api_client.get("/api/courses")
        titles = response.json()["course_titles"]
        assert "MCP Course" in titles
        assert "RAG Fundamentals" in titles
        assert "AI Basics" in titles

    def test_analytics_called_once(self, api_client, mock_rag_system):
        """get_course_analytics() is called exactly once per request"""
        api_client.get("/api/courses")
        mock_rag_system.get_course_analytics.assert_called_once()


# ============================================================================
# GET /api/courses — error handling
# ============================================================================

class TestCoursesEndpointErrors:
    """Error conditions for /api/courses"""

    def test_analytics_exception_returns_500(self, api_client, mock_rag_system):
        """When get_course_analytics() raises, the endpoint returns HTTP 500"""
        mock_rag_system.get_course_analytics.side_effect = Exception("DB error")
        response = api_client.get("/api/courses")
        assert response.status_code == 500

    def test_500_detail_present(self, api_client, mock_rag_system):
        """500 response body includes a ``detail`` field"""
        mock_rag_system.get_course_analytics.side_effect = Exception("DB error")
        response = api_client.get("/api/courses")
        assert "detail" in response.json()


# ============================================================================
# DELETE /api/session/{session_id}
# ============================================================================

class TestSessionDeleteEndpoint:
    """Tests for the DELETE /api/session/{session_id} endpoint"""

    def test_returns_200(self, api_client):
        """DELETE /api/session/<id> returns HTTP 200"""
        response = api_client.delete("/api/session/my-session-id")
        assert response.status_code == 200

    def test_response_body_is_ok(self, api_client):
        """Response body is ``{"status": "ok"}``"""
        response = api_client.delete("/api/session/my-session-id")
        assert response.json() == {"status": "ok"}

    def test_clear_session_called_with_correct_id(self, api_client, mock_rag_system):
        """session_manager.clear_session() is called with the path parameter"""
        api_client.delete("/api/session/abc-123")
        mock_rag_system.session_manager.clear_session.assert_called_once_with("abc-123")

    def test_url_encoded_session_id(self, api_client, mock_rag_system):
        """URL-safe session IDs are handled correctly"""
        api_client.delete("/api/session/session-2025-02-24")
        mock_rag_system.session_manager.clear_session.assert_called_once_with(
            "session-2025-02-24"
        )


# ============================================================================
# Response schema validation
# ============================================================================

class TestResponseSchemas:
    """Verify that response shapes conform to the documented API contract"""

    def test_query_response_schema(self, api_client):
        """query response has exactly the documented top-level keys"""
        response = api_client.post("/api/query", json={"query": "Test"})
        data = response.json()
        assert set(data.keys()) == {"answer", "sources", "session_id"}

    def test_courses_response_schema(self, api_client):
        """courses response has exactly the documented top-level keys"""
        response = api_client.get("/api/courses")
        data = response.json()
        assert set(data.keys()) == {"total_courses", "course_titles"}

    def test_query_answer_is_string(self, api_client):
        """``answer`` field is a string"""
        response = api_client.post("/api/query", json={"query": "Test"})
        assert isinstance(response.json()["answer"], str)

    def test_session_id_is_string(self, api_client):
        """``session_id`` field is a string"""
        response = api_client.post("/api/query", json={"query": "Test"})
        assert isinstance(response.json()["session_id"], str)

    def test_total_courses_is_int(self, api_client):
        """``total_courses`` field is an integer"""
        response = api_client.get("/api/courses")
        assert isinstance(response.json()["total_courses"], int)

    def test_course_titles_are_strings(self, api_client):
        """Every entry in ``course_titles`` is a string"""
        response = api_client.get("/api/courses")
        for title in response.json()["course_titles"]:
            assert isinstance(title, str)
