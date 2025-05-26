import asyncio
import json
import operator
import requests
import time
import typing


from collections import deque
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from pydantic import BaseModel, Field

EVENT_LIMIT = 999
ROLE_DELEGATION = ROLE_MCP_SERVER = "user"

transcript = deque([], maxlen=EVENT_LIMIT)


class F:

    @staticmethod
    def json_schema(e: object):
        return e.model_json_schema()

    @staticmethod
    def joined_row(data: dict):
        s = ""
        for k, v in data.items():
            s += f"{k}: {v}; "

        return s

    @staticmethod
    def joined_col(data: dict):
        pairs = []
        for k, v in data.items():
            pairs.append(f"{k}={v}")

        return ", ".join(pairs)


class MCPOutput(BaseModel):
    action: typing.Literal[
        "call_tool",
        "query_tools",
        "query_prompts",
        "query_resources",
        # "get_prompt",
        "call_prompt",
        # "read_resource",
    ] = Field(
        description="Action to take.",
    )
    name: str | None = Field()
    arguments: dict = Field()

def agent(prompt: str, messages: list[dict]) -> str:
    if not transcript:
        raise Exception("No message?")

    sysprompt: dict = {
        "role": "system",
        "content": f"""You analyze input of each iteration of whatever process you are interacting with."""
        """You have an option to either 'proceed' with the next iteration or use some of the tools available."""
        # f"""Always respond in the following structure ({MCPOutput.model_json_schema()})."""
        """Do not set properties to anything other than null unless absolutely positive that some other value is necessary based on message history.""",
    }

    payload = {
        "model": "deepseek-v2",
        "response_format": "json",
        "format": MCPOutput.model_json_schema(),
        "messages": [sysprompt, {"role": "user", "content": prompt}, *messages],
    }

    print(" <<")
    print(messages[-1])
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

            instruction: str = (
                f"""Our goal: given textual content of a page and a JSON array of all links on it - rate (from 1 to 100) how likely is each link to lead towards a publicly accessible server with an openapi.json schema."""
            )

            context = await session.read_resource("context://current")
            ctx = json.loads(context.contents[0].text)

            print(MCPOutput.model_json_schema())

            transcript.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "reply": """Always use 'proceed' tool call to allow the browser automation to proceed with processing. Don't use anything else unless it makes more sense given the message history.""",
                            "context": ctx,
                        }
                    ),
                }
            )

            while True:
                # instruction: str = input("Ask it to do something: ")
                response = agent(
                    instruction,
                    list(transcript),
                )

                machined = {"role": "assistant", "content": response}
                output = MCPOutput.model_validate(response)

                transcript.append(
                    {"role": "assistance", "content": json.dumps(machined["content"])}
                )

                context = await session.read_resource("context://current")
                ctx = json.loads(context.contents[0].text)

                try:
                    match output.action:
                        case "query_tools":
                            result = await session.list_tools()
                            tools = list(
                                map(
                                    json.loads,
                                    map(operator.methodcaller("json"), result.tools),
                                )
                            )
                            reply = await session.get_prompt(
                                "queried_tools", {"result": str(tools)}
                            )

                            transcript.append(
                                {
                                    "role": ROLE_MCP_SERVER,
                                    "content": json.dumps(
                                        {
                                            "reply": reply.messages[0].content.text,
                                            "tools": tools,
                                            "context": ctx,
                                        }
                                    ),
                                }
                            )

                        case "query_prompts":
                            result = await session.list_prompts()
                            transcript.append(
                                {
                                    "role": ROLE_MCP_SERVER,
                                    "content": json.dumps(
                                        {
                                            "prompts": list(
                                                map(
                                                    json.loads,
                                                    map(
                                                        operator.methodcaller("json"),
                                                        result.prompts,
                                                    ),
                                                )
                                            ),
                                            "context": ctx,
                                        }
                                    ),
                                }
                            )

                        case "query_resources":
                            result = await session.list_resources()
                            transcript.append(
                                {
                                    "role": ROLE_MCP_SERVER,
                                    "content": json.dumps(
                                        {
                                            "resources": list(
                                                map(
                                                    json.loads,
                                                    map(
                                                        operator.methodcaller("json"),
                                                        result.resources,
                                                    ),
                                                )
                                            ),
                                            "context": ctx,
                                        }
                                    ),
                                }
                            )

                        case "call_tool":
                            result = await session.call_tool(output.name, output.arguments)
                            reply = await session.get_prompt(
                                "called_tool", {"result": result.content[0].text}
                            )

                            transcript.append(
                                {
                                    "role": ROLE_MCP_SERVER,
                                    "content": json.dumps(
                                        {
                                            # "reply": reply.messages[0].content.text,
                                            "reply": reply.messages[0].content.text,
                                            "tool_output": result.content[0].text,
                                            "context": ctx,
                                        }
                                    ),
                                },
                            )

                        case "read_resource":
                            result = await session.read_resource(output.name)
                            transcript.append(
                                {
                                    "role": ROLE_MCP_SERVER,
                                    "content": json.dumps(
                                    {
                                        "resource": result.content[0].text,
                                        "context": ctx,
                                    }
                                    ),
                                },
                            )

                        case "call_prompt":
                            result = await session.get_prompt(output.name, output.arguments)
                            transcript.append(
                                {
                                    "role": ROLE_DELEGATION,
                                    "content": json.dumps(
                                        {
                                            "prompt": result.messages[0].content.text,
                                            "response": delegate(
                                                result.messages[0].content.text
                                            ),
                                            "context": ctx,
                                        }
                                    ),
                                },
                            )

                        case _:
                            raise Exception(f"Unknown action {output.action}")

                except Exception as ex:
                    raise ex
                    reply = await session.get_prompt("on_failure", {"ex": str(ex)})

                    transcript.append(
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "reply": reply.messages[
                                        0
                                    ].content.text,  # f"""Exception: {ex}""",
                                    "context": ctx,
                                }
                            ),
                        },
                    )

                time.sleep(0.1)


def delegate(text: str) -> str:
    return "some response from an LLM, IGNORE THIS - it's currently hardocded until back and forth with an LLM is implemented"


if __name__ == "__main__":
    asyncio.run(main())
