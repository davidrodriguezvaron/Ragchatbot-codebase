"""End-to-end RAG pipeline integration tests

Tests the full flow from user query through to response generation,
verifying all components work together correctly.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from rag_system import RAGSystem
from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool
from vector_store import SearchResults


# ============================================================================
# Mock Anthropic Response Classes
# ============================================================================

@dataclass
class MockTextBlock:
    type: str = "text"
    text: str = "This is the AI response."


@dataclass
class MockToolUseBlock:
    type: str = "tool_use"
    id: str = "toolu_01ABC123"
    name: str = "search_course_content"
    input: Dict[str, Any] = None

    def __post_init__(self):
        if self.input is None:
            self.input = {"query": "What is MCP?"}


# ============================================================================
# Config Mock
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration for RAGSystem"""
    config = Mock()
    config.ANTHROPIC_API_KEY = "test-api-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.CHROMA_PATH = "./test_chroma"
    config.MAX_RESULTS = 5
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100
    config.MAX_HISTORY = 2
    return config


# ============================================================================
# RAGSystem Initialization Tests
# ============================================================================

class TestRAGSystemInitialization:
    """Tests for RAGSystem initialization and component setup"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_tool_manager_has_both_tools(
        self, mock_doc_proc, mock_session, mock_ai_gen, mock_vector_store, mock_config
    ):
        """Verify both CourseSearchTool and CourseOutlineTool are registered"""
        rag = RAGSystem(mock_config)

        tool_definitions = rag.tool_manager.get_tool_definitions()
        tool_names = [t["name"] for t in tool_definitions]

        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names
        assert len(tool_names) == 2

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_components_initialized_with_config(
        self, mock_doc_proc, mock_session, mock_ai_gen, mock_vector_store, mock_config
    ):
        """Verify all components receive correct config values"""
        rag = RAGSystem(mock_config)

        mock_vector_store.assert_called_once_with(
            mock_config.CHROMA_PATH,
            mock_config.EMBEDDING_MODEL,
            mock_config.MAX_RESULTS
        )
        mock_ai_gen.assert_called_once_with(
            mock_config.ANTHROPIC_API_KEY,
            mock_config.ANTHROPIC_MODEL
        )
        mock_session.assert_called_once_with(mock_config.MAX_HISTORY)


# ============================================================================
# Query Flow Tests
# ============================================================================

class TestRAGSystemQuery:
    """Tests for RAGSystem.query() method"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_query_passes_tools_to_ai_generator(
        self, mock_doc_proc, mock_session, mock_ai_gen_class, mock_vector_store, mock_config
    ):
        """Verify tools are passed to AIGenerator.generate_response()"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "AI response"
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        rag = RAGSystem(mock_config)
        rag.query("What is MCP?", session_id="test-session")

        # Verify generate_response was called with tools
        call_kwargs = mock_ai_instance.generate_response.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] is not None
        assert len(call_kwargs["tools"]) == 2  # Both tools

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_query_passes_tool_manager(
        self, mock_doc_proc, mock_session, mock_ai_gen_class, mock_vector_store, mock_config
    ):
        """Verify tool_manager is passed to AIGenerator"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "AI response"
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        rag = RAGSystem(mock_config)
        rag.query("What is MCP?")

        call_kwargs = mock_ai_instance.generate_response.call_args[1]
        assert "tool_manager" in call_kwargs
        assert call_kwargs["tool_manager"] is rag.tool_manager

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_query_returns_sources(
        self, mock_doc_proc, mock_session, mock_ai_gen_class, mock_vector_store_class, mock_config
    ):
        """Verify sources are extracted and returned"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "AI response"
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        mock_vs_instance = Mock()
        mock_vector_store_class.return_value = mock_vs_instance

        # Set up search results
        mock_vs_instance.search.return_value = SearchResults(
            documents=["MCP content"],
            metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
            distances=[0.1],
            error=None
        )
        mock_vs_instance.get_lesson_link.return_value = "https://example.com/lesson"

        rag = RAGSystem(mock_config)

        # Manually set sources on the search tool (simulating what happens after tool execution)
        rag.search_tool.last_sources = [
            {"text": "MCP Course - Lesson 1", "link": "https://example.com/lesson"}
        ]

        response, sources = rag.query("What is MCP?")

        assert len(sources) == 1
        assert sources[0]["text"] == "MCP Course - Lesson 1"

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_query_resets_sources_after_retrieval(
        self, mock_doc_proc, mock_session, mock_ai_gen_class, mock_vector_store, mock_config
    ):
        """Verify sources are reset after being retrieved"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "AI response"
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        rag = RAGSystem(mock_config)

        # Set sources
        rag.search_tool.last_sources = [{"text": "Source", "link": "http://test.com"}]

        rag.query("What is MCP?")

        # Sources should be reset after query
        assert rag.search_tool.last_sources == []

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_session_history_updated(
        self, mock_doc_proc, mock_session_class, mock_ai_gen_class, mock_vector_store, mock_config
    ):
        """Verify session manager receives the exchange"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "AI response about MCP"
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session_class.return_value = mock_session_instance

        rag = RAGSystem(mock_config)
        rag.query("What is MCP?", session_id="session-123")

        mock_session_instance.add_exchange.assert_called_once()
        call_args = mock_session_instance.add_exchange.call_args[0]
        assert call_args[0] == "session-123"
        assert "What is MCP?" in call_args[1]
        assert call_args[2] == "AI response about MCP"

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_conversation_history_passed_to_generator(
        self, mock_doc_proc, mock_session_class, mock_ai_gen_class, mock_vector_store, mock_config
    ):
        """Verify conversation history is retrieved and passed"""
        mock_ai_instance = Mock()
        mock_ai_instance.generate_response.return_value = "Follow up response"
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = "User: What is MCP?\nAssistant: MCP is..."
        mock_session_class.return_value = mock_session_instance

        rag = RAGSystem(mock_config)
        rag.query("Tell me more", session_id="session-123")

        call_kwargs = mock_ai_instance.generate_response.call_args[1]
        assert call_kwargs["conversation_history"] == "User: What is MCP?\nAssistant: MCP is..."


# ============================================================================
# Error Propagation Tests
# ============================================================================

class TestRAGSystemErrorHandling:
    """Tests for error handling in RAGSystem"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    def test_query_error_propagation(
        self, mock_doc_proc, mock_session, mock_ai_gen_class, mock_vector_store_class, mock_config
    ):
        """Verify VectorStore errors propagate to response"""
        mock_ai_instance = Mock()
        mock_ai_gen_class.return_value = mock_ai_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        mock_vs_instance = Mock()
        mock_vector_store_class.return_value = mock_vs_instance

        # Simulate search error
        mock_vs_instance.search.return_value = SearchResults.empty("Connection error")

        rag = RAGSystem(mock_config)

        # The error should be passed to the tool result, then to AI
        # AI should receive the error message and handle it
        mock_ai_instance.generate_response.return_value = "I encountered an error searching."

        response, sources = rag.query("What is MCP?")

        # Response should complete (AI handles the error gracefully)
        assert response is not None


# ============================================================================
# Tool Integration Tests
# ============================================================================

class TestToolIntegration:
    """Tests for tool integration within RAG pipeline"""

    def test_course_search_tool_integration(self, mock_vector_store, mock_search_results):
        """Verify CourseSearchTool integrates correctly with VectorStore"""
        mock_vector_store.search.return_value = mock_search_results

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="MCP protocol")

        assert "MCP" in result
        mock_vector_store.search.assert_called_once()

    def test_course_outline_tool_integration(self, mock_vector_store):
        """Verify CourseOutlineTool integrates correctly with VectorStore"""
        tool = CourseOutlineTool(mock_vector_store)
        result = tool.execute(course_title="MCP")

        assert "MCP Course" in result
        assert "Lesson 1" in result
        mock_vector_store.get_course_outline.assert_called_once_with("MCP")

    def test_tool_manager_sources_flow(self, mock_vector_store, mock_search_results):
        """Verify sources flow correctly through ToolManager"""
        mock_vector_store.search.return_value = mock_search_results

        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(search_tool)

        # Execute search
        manager.execute_tool("search_course_content", query="MCP")

        # Get sources
        sources = manager.get_last_sources()
        assert len(sources) > 0

        # Reset
        manager.reset_sources()
        assert manager.get_last_sources() == []


# ============================================================================
# Full Pipeline Simulation Tests
# ============================================================================

class TestFullPipelineSimulation:
    """Simulated end-to-end tests of the full RAG pipeline"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    @patch('ai_generator.anthropic.Anthropic')
    def test_full_query_with_tool_use(
        self, mock_anthropic_class, mock_doc_proc, mock_session, mock_vector_store_class, mock_config
    ):
        """
        Full pipeline test: query -> tool use -> search -> response

        This test simulates the complete flow:
        1. User asks "What is MCP?"
        2. AI decides to use search_course_content tool
        3. Tool executes and returns results
        4. AI generates final response based on results
        """
        # Setup Anthropic mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First response: AI requests tool use
        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            MockToolUseBlock(
                name="search_course_content",
                input={"query": "MCP protocol"}
            )
        ]

        # Second response: AI gives final answer
        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock(text="MCP is a protocol for AI tools.")]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        # Setup VectorStore mock
        mock_vs_instance = Mock()
        mock_vector_store_class.return_value = mock_vs_instance
        mock_vs_instance.search.return_value = SearchResults(
            documents=["MCP (Model Context Protocol) allows AI to use external tools."],
            metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
            distances=[0.1],
            error=None
        )
        mock_vs_instance.get_lesson_link.return_value = "https://example.com/mcp/lesson1"
        mock_vs_instance.get_course_outline.return_value = {
            "title": "MCP Course",
            "course_link": "https://example.com/mcp",
            "lessons": []
        }

        # Setup session mock
        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        # Execute the full pipeline
        rag = RAGSystem(mock_config)
        response, sources = rag.query("What is MCP?", session_id="test-session")

        # Verify results
        assert response == "MCP is a protocol for AI tools."
        assert mock_client.messages.create.call_count == 2

        # Verify tool was executed
        mock_vs_instance.search.assert_called_once()

    @patch('rag_system.VectorStore')
    @patch('rag_system.SessionManager')
    @patch('rag_system.DocumentProcessor')
    @patch('ai_generator.anthropic.Anthropic')
    def test_query_without_tool_use(
        self, mock_anthropic_class, mock_doc_proc, mock_session, mock_vector_store_class, mock_config
    ):
        """
        Test query that AI answers directly without tool use

        For general knowledge questions, AI should respond directly.
        """
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # AI responds directly without tool use
        direct_response = Mock()
        direct_response.stop_reason = "end_turn"
        direct_response.content = [MockTextBlock(text="Hello! How can I help you?")]

        mock_client.messages.create.return_value = direct_response

        mock_vs_instance = Mock()
        mock_vector_store_class.return_value = mock_vs_instance

        mock_session_instance = Mock()
        mock_session_instance.get_conversation_history.return_value = None
        mock_session.return_value = mock_session_instance

        rag = RAGSystem(mock_config)
        response, sources = rag.query("Hello!", session_id="test-session")

        assert response == "Hello! How can I help you?"
        assert mock_client.messages.create.call_count == 1  # Only one call, no tool use
        mock_vs_instance.search.assert_not_called()  # No search performed
