import logging
import os
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Dict, List, Any, Type

from pydantic import create_model, Field
from llama_index.core.tools import FunctionTool

# Official Anthropic MCP SDK
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import mcp.types as types

from private_gpt.database import get_all_mcp_configs

logger = logging.getLogger(__name__)

class MCPManager:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions: Dict[str, ClientSession] = {}
        self.tools_list: List[FunctionTool] = []

    async def startup(self):
        """Called by FastAPI startup. Runs safely on the native uvloop."""
        configs = get_all_mcp_configs()
        if not configs:
            return

        for config in configs:
            try:
                logger.info(f"Connecting to MCP: {config['name']}...")
                async with asyncio.timeout(15.0): 
                    if config["transport_type"] == "stdio":
                        env = os.environ.copy()
                        if config.get("env_vars"):
                            env.update(config["env_vars"])
                        server_params = StdioServerParameters(command=config["command"], args=config.get("args", []), env=env)
                        read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
                    elif config["transport_type"] == "sse":
                        headers = config.get("env_vars", {})
                        read, write = await self.exit_stack.enter_async_context(sse_client(url=config["command"], headers=headers))
                    else:
                        continue

                    session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                    await session.initialize()
                    self.sessions[config["name"]] = session

                    mcp_tools = await session.list_tools()
                    for mcp_tool in mcp_tools.tools:
                        self._register_tool(config["name"], session, mcp_tool)
                        
                    logger.info(f"Successfully initialized MCP: {config['name']} with {len(mcp_tools.tools)} tools.")
            except Exception as e:
                logger.error(f"Failed to initialize MCP Server '{config['name']}': {e}")

    async def shutdown(self):
        await self.exit_stack.aclose()
        logger.info("MCP Manager shutdown complete.")

    def get_all_tools(self) -> List[FunctionTool]:
        return self.tools_list

    def _register_tool(self, server_name: str, session: ClientSession, mcp_tool: types.Tool):
        clean_server_name = server_name.replace(' ', '_').replace('-', '_')
        tool_name = f"{clean_server_name}_{mcp_tool.name}"
        
        # Tools are now strictly async, allowing the native event loop to handle them flawlessly
        async def async_tool_wrapper(**kwargs) -> str:
            logger.info(f"Executing MCP tool '{mcp_tool.name}' via '{server_name}'...")
            try:
                # 60 Second timeout for tool execution
                async with asyncio.timeout(60.0):
                    res = await session.call_tool(mcp_tool.name, arguments=kwargs)
                    return "\n".join([c.text for c in res.content if isinstance(c, types.TextContent)])
            except TimeoutError:
                err = f"Timeout: Tool '{mcp_tool.name}' took too long to respond."
                logger.error(err)
                return err
            except Exception as e:
                logger.error(f"Error calling MCP tool {mcp_tool.name}: {e}")
                return f"Error calling {mcp_tool.name}: {str(e)}"
        
        def sync_tool_wrapper(**kwargs) -> str:
            raise RuntimeError("MCP Tools must be called asynchronously. Ensure astream_chat is used.")
        
        schema = self._generate_pydantic_model(tool_name, mcp_tool.inputSchema)
        
        self.tools_list.append(FunctionTool.from_defaults(
            fn=sync_tool_wrapper,           
            async_fn=async_tool_wrapper,    
            name=tool_name, 
            description=f"[{server_name}] {mcp_tool.description}", 
            fn_schema=schema
        ))

    def _generate_pydantic_model(self, name: str, schema: dict) -> Type[Any]:
        fields = {}
        if schema and "properties" in schema:
            for key, prop in schema["properties"].items():
                prop_type = str
                if prop.get("type") == "integer": prop_type = int
                elif prop.get("type") == "boolean": prop_type = bool
                elif prop.get("type") == "number": prop_type = float
                elif prop.get("type") == "array": prop_type = list
                elif prop.get("type") == "object": prop_type = dict
                
                description = prop.get("description", "")
                
                if "required" in schema and key in schema["required"]:
                    fields[key] = (prop_type, Field(..., description=description))
                else:
                    fields[key] = (prop_type, Field(None, description=description))
                    
        return create_model(f"{name}_schema", **fields)