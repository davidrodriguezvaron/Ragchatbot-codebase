"""Tests for CourseSearchTool, CourseOutlineTool, and ToolManager"""

import pytest
from unittest.mock import Mock, call
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


# ============================================================================
# CourseSearchTool.execute() Tests
# ============================================================================

class TestCourseSearchToolExecute:
    """Tests for CourseSearchTool.execute() method"""

    def test_execute_returns_formatted_results(self, mock_vector_store, mock_search_results):
        """Verify successful search returns formatted string with course/lesson headers"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results

        result = tool.execute(query="What is MCP?")

        assert "[MCP Course - Lesson 1]" in result
        assert "[MCP Course - Lesson 2]" in result
        assert "[RAG Fundamentals - Lesson 1]" in result
        assert "MCP (Model Context Protocol)" in result
        mock_vector_store.search.assert_called_once_with(
            query="What is MCP?",
            course_name=None,
            lesson_number=None
        )

    def test_execute_empty_results_returns_message(self, mock_vector_store, empty_search_results):
        """Verify empty SearchResults returns 'No relevant content found' message"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = empty_search_results

        result = tool.execute(query="nonexistent topic")

        assert "No relevant content found" in result

    def test_execute_empty_results_with_filters(self, mock_vector_store, empty_search_results):
        """Verify empty results include filter info in message"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = empty_search_results

        result = tool.execute(
            query="nonexistent topic",
            course_name="MCP Course",
            lesson_number=5
        )

        assert "No relevant content found" in result
        assert "MCP Course" in result
        assert "lesson 5" in result

    def test_execute_error_returns_error_message(self, mock_vector_store, error_search_results):
        """Verify SearchResults.error is returned directly"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = error_search_results

        result = tool.execute(query="anything")

        assert result == "No course found matching 'NonExistent'"

    def test_execute_with_course_filter(self, mock_vector_store, mock_search_results):
        """Verify course_name is passed to VectorStore.search()"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results

        tool.execute(query="What is MCP?", course_name="MCP Course")

        mock_vector_store.search.assert_called_once_with(
            query="What is MCP?",
            course_name="MCP Course",
            lesson_number=None
        )

    def test_execute_with_lesson_filter(self, mock_vector_store, mock_search_results):
        """Verify lesson_number is passed to VectorStore.search()"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results

        tool.execute(query="What is MCP?", lesson_number=2)

        mock_vector_store.search.assert_called_once_with(
            query="What is MCP?",
            course_name=None,
            lesson_number=2
        )

    def test_execute_with_both_filters(self, mock_vector_store, mock_search_results):
        """Verify both filters are passed together"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results

        tool.execute(query="What is MCP?", course_name="MCP Course", lesson_number=1)

        mock_vector_store.search.assert_called_once_with(
            query="What is MCP?",
            course_name="MCP Course",
            lesson_number=1
        )


class TestCourseSearchToolFormatResults:
    """Tests for CourseSearchTool._format_results() and source tracking"""

    def test_format_results_tracks_sources(self, mock_vector_store, mock_search_results):
        """Verify last_sources is populated with unique sources"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results

        tool.execute(query="What is MCP?")

        # Should have 3 unique sources (2 from MCP Course, 1 from RAG Fundamentals)
        assert len(tool.last_sources) == 3
        # Check structure
        for source in tool.last_sources:
            assert "text" in source
            assert "link" in source

    def test_format_results_deduplicates_sources(self, mock_vector_store):
        """Verify duplicate course/lesson combinations are deduplicated"""
        tool = CourseSearchTool(mock_vector_store)

        # Create results with duplicate course/lesson
        duplicate_results = SearchResults(
            documents=["Content 1", "Content 2"],
            metadata=[
                {"course_title": "MCP Course", "lesson_number": 1, "chunk_index": 0},
                {"course_title": "MCP Course", "lesson_number": 1, "chunk_index": 1},  # Same lesson
            ],
            distances=[0.1, 0.2],
            error=None
        )
        mock_vector_store.search.return_value = duplicate_results

        tool.execute(query="MCP")

        # Should only have 1 unique source
        assert len(tool.last_sources) == 1
        assert tool.last_sources[0]["text"] == "MCP Course - Lesson 1"

    def test_format_results_gets_lesson_links(self, mock_vector_store, mock_search_results):
        """Verify get_lesson_link() is called for each result"""
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson"

        tool.execute(query="What is MCP?")

        # get_lesson_link should be called for each unique source with a lesson number
        assert mock_vector_store.get_lesson_link.call_count >= 1


class TestCourseSearchToolDefinition:
    """Tests for CourseSearchTool.get_tool_definition()"""

    def test_get_tool_definition_structure(self, mock_vector_store, search_tool_definition):
        """Verify tool definition matches expected structure"""
        tool = CourseSearchTool(mock_vector_store)

        definition = tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert definition["input_schema"]["required"] == ["query"]
        assert "query" in definition["input_schema"]["properties"]
        assert "course_name" in definition["input_schema"]["properties"]
        assert "lesson_number" in definition["input_schema"]["properties"]


# ============================================================================
# CourseOutlineTool Tests
# ============================================================================

class TestCourseOutlineTool:
    """Tests for CourseOutlineTool"""

    def test_execute_returns_formatted_outline(self, mock_vector_store):
        """Verify outline is formatted correctly"""
        tool = CourseOutlineTool(mock_vector_store)

        result = tool.execute(course_title="MCP")

        assert "Course: MCP Course" in result
        assert "Link: https://example.com/mcp" in result
        assert "Lesson 1: Introduction to MCP" in result
        assert "Lesson 2: Tool Definitions" in result
        assert "Lessons (2 total):" in result

    def test_execute_not_found_returns_message(self, mock_vector_store):
        """Verify not found message when course doesn't exist"""
        tool = CourseOutlineTool(mock_vector_store)
        mock_vector_store.get_course_outline.return_value = None

        result = tool.execute(course_title="NonExistent")

        assert "No course found matching 'NonExistent'" in result

    def test_get_tool_definition_structure(self, mock_vector_store, outline_tool_definition):
        """Verify tool definition matches expected structure"""
        tool = CourseOutlineTool(mock_vector_store)

        definition = tool.get_tool_definition()

        assert definition["name"] == "get_course_outline"
        assert "outline" in definition["description"].lower() or "syllabus" in definition["description"].lower()
        assert definition["input_schema"]["required"] == ["course_title"]


# ============================================================================
# ToolManager Tests
# ============================================================================

class TestToolManager:
    """Tests for ToolManager"""

    def test_register_tool(self, mock_vector_store):
        """Verify tools are registered correctly"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)

        manager.register_tool(tool)

        assert "search_course_content" in manager.tools

    def test_register_multiple_tools(self, mock_vector_store):
        """Verify multiple tools can be registered"""
        manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        outline_tool = CourseOutlineTool(mock_vector_store)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        assert len(manager.tools) == 2
        assert "search_course_content" in manager.tools
        assert "get_course_outline" in manager.tools

    def test_get_tool_definitions(self, mock_vector_store):
        """Verify get_tool_definitions returns all tool definitions"""
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))
        manager.register_tool(CourseOutlineTool(mock_vector_store))

        definitions = manager.get_tool_definitions()

        assert len(definitions) == 2
        names = [d["name"] for d in definitions]
        assert "search_course_content" in names
        assert "get_course_outline" in names

    def test_execute_tool_dispatches_correctly(self, mock_vector_store, mock_search_results):
        """Verify execute_tool calls the right tool with kwargs"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results
        manager.register_tool(tool)

        result = manager.execute_tool("search_course_content", query="What is MCP?")

        assert "[MCP Course" in result
        mock_vector_store.search.assert_called_once()

    def test_execute_tool_unknown_tool_returns_error(self):
        """Verify unknown tool name returns error string"""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "not found" in result.lower()
        assert "nonexistent_tool" in result

    def test_get_last_sources_returns_sources(self, mock_vector_store, mock_search_results):
        """Verify sources are retrieved from tool"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results
        manager.register_tool(tool)

        # Execute a search to populate sources
        manager.execute_tool("search_course_content", query="MCP")
        sources = manager.get_last_sources()

        assert len(sources) > 0

    def test_get_last_sources_empty_when_no_search(self, mock_vector_store):
        """Verify empty sources when no search performed"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        sources = manager.get_last_sources()

        assert sources == []

    def test_reset_sources_clears_all(self, mock_vector_store, mock_search_results):
        """Verify reset_sources clears last_sources"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        mock_vector_store.search.return_value = mock_search_results
        manager.register_tool(tool)

        # Execute search then reset
        manager.execute_tool("search_course_content", query="MCP")
        assert len(manager.get_last_sources()) > 0

        manager.reset_sources()

        assert manager.get_last_sources() == []
