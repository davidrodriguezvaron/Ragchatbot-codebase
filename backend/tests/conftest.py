"""Shared fixtures for RAG chatbot tests"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vector_store import SearchResults


# ============================================================================
# Mock Data Factories
# ============================================================================

@pytest.fixture
def sample_documents():
    """Sample document content for tests"""
    return [
        "MCP (Model Context Protocol) is a standardized way to connect AI models to external tools.",
        "Claude can use tools through the Anthropic API by specifying tool definitions.",
        "RAG systems retrieve relevant documents before generating responses."
    ]


@pytest.fixture
def sample_metadata():
    """Sample metadata matching the documents"""
    return [
        {"course_title": "MCP Course", "lesson_number": 1, "chunk_index": 0},
        {"course_title": "MCP Course", "lesson_number": 2, "chunk_index": 0},
        {"course_title": "RAG Fundamentals", "lesson_number": 1, "chunk_index": 0}
    ]


@pytest.fixture
def sample_distances():
    """Sample distance scores (lower = more relevant)"""
    return [0.15, 0.25, 0.35]


# ============================================================================
# SearchResults Fixtures
# ============================================================================

@pytest.fixture
def mock_search_results(sample_documents, sample_metadata, sample_distances):
    """Factory for creating SearchResults with test data"""
    return SearchResults(
        documents=sample_documents,
        metadata=sample_metadata,
        distances=sample_distances,
        error=None
    )


@pytest.fixture
def empty_search_results():
    """Empty SearchResults (no documents found)"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error=None
    )


@pytest.fixture
def error_search_results():
    """SearchResults with error"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[],
        error="No course found matching 'NonExistent'"
    )


# ============================================================================
# VectorStore Mock
# ============================================================================

@pytest.fixture
def mock_vector_store(mock_search_results):
    """Mocked VectorStore with configurable behavior"""
    store = Mock()
    store.search.return_value = mock_search_results
    store.get_lesson_link.return_value = "https://example.com/lesson/1"
    store.get_course_outline.return_value = {
        "title": "MCP Course",
        "course_link": "https://example.com/mcp",
        "lessons": [
            {"lesson_number": 1, "lesson_title": "Introduction to MCP"},
            {"lesson_number": 2, "lesson_title": "Tool Definitions"}
        ]
    }
    return store


# ============================================================================
# Anthropic Response Mocks
# ============================================================================

@dataclass
class MockTextBlock:
    """Mock for Anthropic TextBlock"""
    type: str = "text"
    text: str = "This is a response about MCP."


@dataclass
class MockToolUseBlock:
    """Mock for Anthropic ToolUseBlock"""
    type: str = "tool_use"
    id: str = "toolu_01ABC123"
    name: str = "search_course_content"
    input: Dict[str, Any] = None

    def __post_init__(self):
        if self.input is None:
            self.input = {"query": "What is MCP?"}


@pytest.fixture
def mock_text_response():
    """Mock Anthropic response with text only (no tool use)"""
    response = Mock()
    response.stop_reason = "end_turn"
    response.content = [MockTextBlock()]
    return response


@pytest.fixture
def mock_tool_use_response():
    """Mock Anthropic response requesting tool use"""
    response = Mock()
    response.stop_reason = "tool_use"
    response.content = [
        MockTextBlock(text="Let me search for that."),
        MockToolUseBlock()
    ]
    return response


@pytest.fixture
def mock_final_response():
    """Mock Anthropic response after tool execution"""
    response = Mock()
    response.stop_reason = "end_turn"
    response.content = [MockTextBlock(text="MCP is a protocol for connecting AI to tools.")]
    return response


# ============================================================================
# Config Mock
# ============================================================================

@pytest.fixture
def sample_config():
    """Test configuration with dummy values"""
    config = Mock()
    config.anthropic_api_key = "test-api-key"
    config.model = "claude-sonnet-4-20250514"
    config.embedding_model = "all-MiniLM-L6-v2"
    config.chroma_path = "./test_chroma_db"
    config.max_results = 5
    config.chunk_size = 800
    config.chunk_overlap = 100
    return config


# ============================================================================
# Tool Manager Fixtures
# ============================================================================

@pytest.fixture
def mock_tool_manager():
    """Mock ToolManager for testing AIGenerator"""
    manager = Mock()
    manager.execute_tool.return_value = "[MCP Course - Lesson 1]\nMCP is a standardized protocol..."
    manager.get_last_sources.return_value = [
        {"text": "MCP Course - Lesson 1", "link": "https://example.com/lesson/1"}
    ]
    manager.reset_sources.return_value = None
    return manager


# ============================================================================
# Tool Definition Fixtures
# ============================================================================

@pytest.fixture
def search_tool_definition():
    """Expected tool definition for search_course_content"""
    return {
        "name": "search_course_content",
        "description": "Search course materials with smart course name matching and lesson filtering",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in the course content"
                },
                "course_name": {
                    "type": "string",
                    "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')"
                },
                "lesson_number": {
                    "type": "integer",
                    "description": "Specific lesson number to search within (e.g. 1, 2, 3)"
                }
            },
            "required": ["query"]
        }
    }


@pytest.fixture
def outline_tool_definition():
    """Expected tool definition for get_course_outline"""
    return {
        "name": "get_course_outline",
        "description": (
            "Get the outline/syllabus/structure of a course, including its "
            "list of lessons. Use this when the user asks about what lessons "
            "are in a course, the course structure, or course syllabus."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "course_title": {
                    "type": "string",
                    "description": "Course title or partial name (e.g. 'MCP', 'computer use')"
                }
            },
            "required": ["course_title"]
        }
    }
