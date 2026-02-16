import anthropic
from typing import List, Optional, Dict, Any
from config import config

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """You are an AI assistant specialized in course materials and educational content. You have access to two tools:

1. **search_course_content** — Search within course lesson content for specific topics, concepts, or details.
2. **get_course_outline** — Retrieve a course's outline including its title, link, and full list of lessons.

Tool Selection Guide:
- **Course outline/structure/syllabus questions** (e.g. "What lessons are in…", "Show me the outline for…", "What does the course cover?"): Use `get_course_outline`
- **Course content/topic questions** (e.g. "What is MCP?", "Explain how…", "What does lesson 3 cover?"): Use `search_course_content`
- **General knowledge questions** (not about specific course materials): Answer directly without using any tool

Tool Usage Rules:
- **Up to 2 tool calls per query**: Use multiple calls when needed for cross-referencing, follow-up searches, or multi-step lookups
- **Prefer single calls**: Only make additional calls if results are genuinely insufficient
- If a tool returns no results, state this clearly without guessing or offering alternatives

Response Protocol:
- When responding to outline queries, include the course title, course link, and each lesson's number and title
- **No meta-commentary**: Provide direct answers only — no reasoning process, search explanations, or question-type analysis
- Do not mention "based on the search results" or similar phrases

All responses must be:
1. **Brief, concise and focused** — Get to the point quickly
2. **Educational** — Maintain instructional value
3. **Clear** — Use accessible language
4. **Example-supported** — Include relevant examples when they aid understanding
5. **Single unified response** — Combine all findings into one cohesive answer; never use horizontal rules (---) or treat tool results as separate sections
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def _serialize_content_blocks(self, content_blocks) -> List[Dict]:
        """
        Convert SDK ContentBlock objects to serializable dicts for API messages.

        Args:
            content_blocks: List of ContentBlock objects from SDK response

        Returns:
            List of dicts suitable for API message content
        """
        content_dicts = []
        for block in content_blocks:
            if block.type == "tool_use":
                content_dicts.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
            elif block.type == "text":
                content_dicts.append({
                    "type": "text",
                    "text": block.text
                })
        return content_dicts

    def _extract_text_response(self, response) -> str:
        """
        Extract text from response content blocks.

        Args:
            response: API response object

        Returns:
            First text block content, or empty string if none found
        """
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _execute_tools(self, response, tool_manager) -> List[Dict]:
        """
        Execute all tool calls in a response.

        Args:
            response: API response containing tool_use blocks
            tool_manager: Manager to execute tools

        Returns:
            List of tool_result dicts
        """
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name,
                    **content_block.input
                )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": content_block.id,
                    "content": tool_result
                })
        return tool_results

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool call rounds.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Initialize messages with user query
        messages = [{"role": "user", "content": query}]

        # Build base API params for this request
        api_params = {
            **self.base_params,
            "system": system_content
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        round_count = 0

        while round_count < config.MAX_TOOL_ROUNDS:
            # Make API call with current messages
            api_params["messages"] = messages
            response = self.client.messages.create(**api_params)

            # If not a tool_use response or no tool_manager, return text
            if response.stop_reason != "tool_use" or not tool_manager:
                return self._extract_text_response(response)

            # Serialize assistant response and append to messages
            messages.append({
                "role": "assistant",
                "content": self._serialize_content_blocks(response.content)
            })

            # Execute tools and append results
            tool_results = self._execute_tools(response, tool_manager)
            messages.append({"role": "user", "content": tool_results})

            round_count += 1

        # Max rounds exhausted - get final response without tool_choice
        # to encourage Claude to respond with text
        final_params = {
            **api_params,
            "messages": messages
        }
        # Remove tool_choice to let Claude naturally conclude
        final_params.pop("tool_choice", None)

        final_response = self.client.messages.create(**final_params)
        return self._extract_text_response(final_response)
