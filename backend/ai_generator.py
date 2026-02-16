import anthropic
from typing import List, Optional, Dict, Any

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
- **One tool call per query maximum**
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
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
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
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.
        
        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            
        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()

        # Convert ContentBlock objects to serializable dicts for the assistant response
        content_dicts = []
        for block in initial_response.content:
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

        # Add AI's tool use response with serialized content
        messages.append({"role": "assistant", "content": content_dicts})
        
        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
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
        
        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        
        # Prepare final API call - include tools if present in original call
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"]
        }
        # Include tools if present (required when message history contains tool_use/tool_result)
        if "tools" in base_params:
            final_params["tools"] = base_params["tools"]
        
        # Get final response
        final_response = self.client.messages.create(**final_params)
        return final_response.content[0].text