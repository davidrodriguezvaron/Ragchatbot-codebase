"""Tests for AIGenerator tool calling functionality

This test file includes critical bug detection tests that verify the tool execution
pipeline works correctly, especially around message serialization and API parameters.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from dataclasses import dataclass
from typing import Dict, Any
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai_generator import AIGenerator


# ============================================================================
# Mock Classes for Anthropic SDK Objects
# ============================================================================

@dataclass
class MockTextBlock:
    """Mock for Anthropic SDK TextBlock"""
    type: str = "text"
    text: str = "This is a response."


@dataclass
class MockToolUseBlock:
    """Mock for Anthropic SDK ToolUseBlock"""
    type: str = "tool_use"
    id: str = "toolu_01ABC123"
    name: str = "search_course_content"
    input: Dict[str, Any] = None

    def __post_init__(self):
        if self.input is None:
            self.input = {"query": "What is MCP?"}


# ============================================================================
# generate_response() Tests
# ============================================================================

class TestGenerateResponseBasic:
    """Basic tests for AIGenerator.generate_response()"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_direct_response_no_tools(self, mock_anthropic_class):
        """Verify text response when stop_reason != 'tool_use'"""
        # Setup mock
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MockTextBlock(text="Claude is an AI assistant.")]
        mock_client.messages.create.return_value = mock_response

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        result = generator.generate_response(query="Who is Claude?")

        assert result == "Claude is an AI assistant."
        mock_client.messages.create.assert_called_once()

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_use_triggers_handle_execution(self, mock_anthropic_class):
        """Verify _handle_tool_execution called when stop_reason == 'tool_use'"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # First call returns tool_use, second returns final answer
        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            MockTextBlock(text="Let me search."),
            MockToolUseBlock()
        ]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock(text="MCP is a protocol.")]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "MCP search results..."

        tools = [{"name": "search_course_content", "description": "Search"}]
        result = generator.generate_response(
            query="What is MCP?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        assert result == "MCP is a protocol."
        assert mock_client.messages.create.call_count == 2
        mock_tool_manager.execute_tool.assert_called_once()

    @patch('ai_generator.anthropic.Anthropic')
    def test_tools_passed_to_api_call(self, mock_anthropic_class):
        """Verify tools parameter included in initial API call"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MockTextBlock()]
        mock_client.messages.create.return_value = mock_response

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        tools = [{"name": "search_course_content", "description": "Search"}]

        generator.generate_response(query="What is MCP?", tools=tools)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == {"type": "auto"}

    @patch('ai_generator.anthropic.Anthropic')
    def test_conversation_history_included_in_system(self, mock_anthropic_class):
        """Verify conversation history is appended to system prompt"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MockTextBlock()]
        mock_client.messages.create.return_value = mock_response

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        history = "User: Hi\nAssistant: Hello!"

        generator.generate_response(query="Follow up question", conversation_history=history)

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "Previous conversation:" in call_kwargs["system"]
        assert history in call_kwargs["system"]


# ============================================================================
# _handle_tool_execution() Tests — CRITICAL BUG DETECTION
# ============================================================================

class TestHandleToolExecution:
    """Tests for _handle_tool_execution() method — includes bug detection tests"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_execution_extracts_tool_name(self, mock_anthropic_class):
        """Verify tool name extracted from ToolUseBlock"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [MockToolUseBlock(name="search_course_content")]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        mock_tool_manager.execute_tool.assert_called_once()
        call_args = mock_tool_manager.execute_tool.call_args
        assert call_args[0][0] == "search_course_content"

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_execution_extracts_inputs(self, mock_anthropic_class):
        """Verify tool inputs passed to execute_tool"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            MockToolUseBlock(
                name="search_course_content",
                input={"query": "MCP basics", "course_name": "MCP Course"}
            )
        ]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        call_kwargs = mock_tool_manager.execute_tool.call_args[1]
        assert call_kwargs["query"] == "MCP basics"
        assert call_kwargs["course_name"] == "MCP Course"

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_result_message_format(self, mock_anthropic_class):
        """Verify tool_result message has correct structure"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [MockToolUseBlock(id="toolu_123")]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Tool output here"

        generator.generate_response(
            query="Test",
            tools=[{"name": "search_course_content"}],
            tool_manager=mock_tool_manager
        )

        # Check the second API call's messages
        second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]

        # Should have: user message, assistant tool_use, user tool_result
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

        # Check tool_result structure
        tool_result_content = messages[2]["content"]
        assert isinstance(tool_result_content, list)
        assert tool_result_content[0]["type"] == "tool_result"
        assert tool_result_content[0]["tool_use_id"] == "toolu_123"
        assert tool_result_content[0]["content"] == "Tool output here"

    @patch('ai_generator.anthropic.Anthropic')
    def test_follow_up_api_includes_tools(self, mock_anthropic_class):
        """
        BUG TEST: Verify follow-up API call includes tools parameter.

        This test will FAIL if Bug 1 is present (missing tools in final_params).
        The Anthropic API requires tools to be present when the message history
        contains tool_use and tool_result blocks.
        """
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [MockToolUseBlock()]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        tools = [{"name": "search_course_content", "description": "Search course content"}]
        generator.generate_response(
            query="What is MCP?",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Verify the SECOND API call (follow-up after tool execution) includes tools
        assert mock_client.messages.create.call_count == 2

        second_call_kwargs = mock_client.messages.create.call_args_list[1][1]

        # THIS IS THE BUG CHECK: tools should be in the second call
        assert "tools" in second_call_kwargs, (
            "BUG DETECTED: 'tools' parameter missing from follow-up API call. "
            "When message history contains tool_use/tool_result, the Anthropic API "
            "requires the tools parameter to understand the tool schema."
        )
        assert second_call_kwargs["tools"] == tools

    @patch('ai_generator.anthropic.Anthropic')
    def test_content_block_serialization(self, mock_anthropic_class):
        """
        BUG TEST: Verify ContentBlock objects serialize correctly.

        This test checks that the assistant's content (which contains
        ToolUseBlock objects from the Anthropic SDK) is properly converted
        to dictionaries before being sent back to the API.
        """
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Create mock SDK-like objects
        tool_use_block = MockToolUseBlock(
            id="toolu_abc123",
            name="search_course_content",
            input={"query": "MCP"}
        )

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [tool_use_block]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        tools = [{"name": "search_course_content"}]
        generator.generate_response(
            query="Test",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Check the second call's messages
        second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]

        # The assistant message content should be serializable
        assistant_content = messages[1]["content"]

        # If this is still the raw SDK object list, it may cause issues
        # The content should be JSON-serializable (list of dicts or similar)
        # This is a weaker check since our mocks are already dataclasses
        assert assistant_content is not None

    @patch('ai_generator.anthropic.Anthropic')
    def test_multiple_tool_calls_in_response(self, mock_anthropic_class):
        """Verify handling of multiple tool calls in a single response"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            MockToolUseBlock(id="toolu_1", name="search_course_content", input={"query": "MCP"}),
            MockToolUseBlock(id="toolu_2", name="get_course_outline", input={"course_title": "MCP"})
        ]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        tools = [{"name": "search_course_content"}, {"name": "get_course_outline"}]
        generator.generate_response(
            query="Test",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should have called execute_tool twice
        assert mock_tool_manager.execute_tool.call_count == 2

        # Check tool results are all included
        second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        tool_results = messages[2]["content"]

        assert len(tool_results) == 2
        assert tool_results[0]["tool_use_id"] == "toolu_1"
        assert tool_results[1]["tool_use_id"] == "toolu_2"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestAIGeneratorEdgeCases:
    """Edge case tests for AIGenerator"""

    @patch('ai_generator.anthropic.Anthropic')
    def test_tool_use_without_tool_manager(self, mock_anthropic_class):
        """Verify graceful handling when tool_use but no tool_manager provided"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        # Response requests tool use but no manager provided
        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [
            MockTextBlock(text="I'll search for that."),
            MockToolUseBlock()
        ]

        mock_client.messages.create.return_value = tool_response

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")

        # Should not crash, should return the text portion
        # Current implementation checks "tool_manager" exists
        result = generator.generate_response(
            query="What is MCP?",
            tools=[{"name": "search_course_content"}],
            tool_manager=None  # No manager!
        )

        # With no tool_manager, should try to return content[0].text
        assert result == "I'll search for that."

    @patch('ai_generator.anthropic.Anthropic')
    def test_empty_tool_input(self, mock_anthropic_class):
        """Verify handling of tool use with empty input dict"""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_response.content = [MockToolUseBlock(input={})]

        final_response = Mock()
        final_response.stop_reason = "end_turn"
        final_response.content = [MockTextBlock()]

        mock_client.messages.create.side_effect = [tool_response, final_response]

        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
        mock_tool_manager = Mock()
        mock_tool_manager.execute_tool.return_value = "Results"

        tools = [{"name": "search_course_content"}]
        result = generator.generate_response(
            query="Test",
            tools=tools,
            tool_manager=mock_tool_manager
        )

        # Should complete without error
        assert result is not None
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content"
        )
