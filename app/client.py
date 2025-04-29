import asyncio
import json
import operator
import requests
import time
import typing


from collections import deque
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from pydantic import BaseModel

EVENT_LIMIT = 30
ROLE_DELEGATION = ROLE_MCP_SERVER = "user"


class F:

    @staticmethod
    def json_schema(e: object):
        return e.model_json_schema()


class MCPOutput(BaseModel):
    action: typing.Literal[
        "list_tools",
        "list_prompts",
        "list_resources",
        "call_tool",
        "get_prompt",
        "read_resource",
    ]
    tool_name: str | None
    resource_name: str | None
    prompt_name: str | None
    arguments: dict


def agent(prompt: str, transcript: dict) -> str:
    if not transcript:
        raise Exception("No message?")

    sysprompt: dict = {
        "role": "system",
        "content": f"""You are an AI agent.

        You have MCP (model context protocol) tools, resources, and prompts at your disposal.
        These are colloquially called "MCP instruments".

        You can ask for available instruments with the appropriate action, then use them appropriately.
        This is the expected structure for all responses: {MCPOutput.model_json_schema()}.

        Don't respond with non-existent combinations of instruments and various parameters.
        Beware that a single instrument is almost never enough to accomplish a goal.
        
        Solve problems from top to bottom - if solving minutiae will not help achieving the goal, do something else.
        Must respond with only a JSON document on a single line, nothing else.""",
    }

    payload = {
        "model": "deepseek-v2",
        "response_format": "json",
        "format": MCPOutput.model_json_schema(),
        "messages": [sysprompt, {"role": "user", "content": prompt}, *transcript],
    }

    print(" <<")
    print(transcript[-1])
    print("\n\n--\n\n")

    with requests.Session().post(
        "http://127.0.0.1:11434/api/chat",
        json=payload,
        stream=True,
    ) as resp:
        if resp.status_code not in [200]:
            print(len(transcript))
            raise Exception(resp.text)

        lines = []
        print(">> ")

        for line in resp.iter_lines():
            content = json.loads(line.decode("utf-8")).get("message", {}).get("content")
            print(content, flush=True, end="")
            lines.append(content)

        return json.loads("".join(filter(None, lines)))


async def main():
    async with stdio_client(
        StdioServerParameters(command="python3", args=["app/server.py"], env=None)
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            instruction: str = f"""Please use the given instruments to crawl the web at a reasonable pace and look for paths ending with .../openapi.json.
            Try to optimize navigation in order to increase chances of finding such paths.
            If OpenAPI schema files are found, use report_found_schema tool to report them in.
            """

            transcript: str = [
                {
                    "role": "user",
                    "content": "choose MCP instruments to accomplish the goal",
                }
            ]

            while True:
                # instruction: str = input("Ask it to do something: ")
                response = agent(
                    instruction,
                    transcript,
                )

                machined = {"role": "assistant", "content": response}
                output = MCPOutput.model_validate(response)

                ctx = await session.read_resource("context://current")
                ctxstr = f"; and current context is {ctx}"

                try:
                    if "list_tools" == output.action:
                        result = await session.list_tools()
                        transcript = [
                            {
                                "role": ROLE_MCP_SERVER,
                                "content": json.dumps(
                                    list(map(F.json_schema, result.tools))
                                )
                                + ctxstr,
                            }
                        ]

                    if "list_prompts" == output.action:
                        result = await session.list_prompts()
                        transcript = [
                            {
                                "role": ROLE_MCP_SERVER,
                                "content": json.dumps(
                                    list(map(F.json_schema, result.prompts))
                                )
                                + ctxstr,
                            }
                        ]

                    if "list_resources" == output.action:
                        result = await session.list_resources()
                        transcript = [
                            {
                                "role": ROLE_MCP_SERVER,
                                "content": json.dumps(
                                    list(map(F.json_schema, result.resources))
                                )
                                + ctxstr,
                            }
                        ]

                    if "call_tool" == output.action:
                        result = await session.call_tool(
                            output.tool_name, output.arguments
                        )
                        transcript = [
                            {
                                "role": ROLE_MCP_SERVER,
                                "content": result.content[0].text + ctxstr,
                            },
                        ]

                    if "read_resource" == output.action:
                        result = await session.read_resource(output.resource_name)
                        transcript = [
                            {
                                "role": ROLE_MCP_SERVER,
                                "content": result.content[0].text + ctxstr,
                            },
                        ]

                    if "get_prompt" == output.action:
                        result = await session.get_prompt(
                            output.prompt_name, output.arguments
                        )
                        transcript = [
                            {
                                "role": ROLE_DELEGATION,
                                "content": delegate(result.content[0].text) + ctxstr,
                            },
                        ]

                except Exception as ex:
                    transcript = [
                        {
                            "role": "user",
                            "content": f"""Exception: {ex}""",
                        },
                    ]

                time.sleep(1)


def delegate(text: str) -> str:
    return "some response from llm"


if __name__ == "__main__":
    asyncio.run(main())
