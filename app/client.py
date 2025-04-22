import asyncio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

async def main():
    async with stdio_client(StdioServerParameters()) as (read, write):
        

asyncio.run(main())
