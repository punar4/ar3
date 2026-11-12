"""Demo: an AI agent asks AR3, over MCP, whether to retry failed PayPal payments.
Run: python agent_demo.py"""
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CASES = [
    ("Capture failed: TRANSACTION_REFUSED (live checkout)",
     dict(error_code="TRANSACTION_REFUSED", channel="LIVE_CHECKOUT")),
    ("Capture failed: INTERNAL_SERVER_ERROR (live checkout)",
     dict(error_code="INTERNAL_SERVER_ERROR", channel="LIVE_CHECKOUT", payment_id="order-5ABC123")),
    ("Capture failed: ORDER_ALREADY_CAPTURED (subscription)",
     dict(error_code="ORDER_ALREADY_CAPTURED", channel="RECURRING")),
]


async def main() -> None:
    server = StdioServerParameters(command=sys.executable, args=["ar3_mcp.py"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Agent connected to AR3. Tools:", ", ".join(t.name for t in tools.tools), "\n")
            for title, args in CASES:
                print(f"Agent: {title}")
                print("Agent: asking AR3 before retrying...")
                result = await session.call_tool("decide_failed_payment", args)
                data = json.loads(result.content[0].text)
                print(f"AR3:   {data.get('action')}  ({data.get('reason', '')[:90]})")
                print(f"AR3 tells the agent: {data.get('agent_instruction')}\n")


asyncio.run(main())
