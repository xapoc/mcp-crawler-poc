import pydantic
import random
import time
import typing

from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP
from os.path import dirname, join
from pydantic import BaseModel, Field, HttpUrl

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options

mcp = FastMCP("OpenAPI Seeker")  # , log_level="ERROR")


class LinkData(BaseModel):
    href: HttpUrl
    text: str
    chance: int = Field(gt=0, le=100)


@dataclass
class Walker:

    # the actual browser
    driver: webdriver.Firefox

    # locations, in memory, to look at
    locations: dict[HttpUrl, LinkData]

    @classmethod
    def create(cls):
        options = Options()
        options.add_argument("--headless")

        options.set_preference(
            "general.useragent.override",
            "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0",
        )
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("javascript.enabled", False)

        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(60)

        return cls(driver, {})

    def estimated(self, estimations: dict[HttpUrl, LinkData] | None) -> None:
        if estimations is None:
            return None

        for uri, link in estimations.items():
            self.locations[uri] = link

    def location(self):
        if not any(self.locations):
            tld = random.choice(
                open(join(dirname(__file__), "resources/tlds.txt")).read().splitlines()
            )
            word = random.choice(open("/usr/share/dict/words").read().splitlines())

            if random.randint(1, 300) == 30:
                return f"https://ddg.gg/?q={word}"

            return f"http://{word}.{tld}"

        return sorted(
            random.shuffle(list(self.locations.values())),
            key=lambda e: e["chance"],
            reverse=True,
        )

    def follow(self, url: str) -> None:
        self.driver.get(url)
        time.sleep(random.randint(0, 30))

    def collect_links(self) -> dict[HttpUrl, LinkData]:
        links = []
        for e in self.driver.find_elements(By.CSS_SELECTOR, "a"):
            links.append(dict(href=e.get_attribute("href"), text=e.text, chance=0))

        return links

    def collect_text(self, page: int):
        body = self.driver.find_element(By.CSS_SELECTOR, "body")
        if body is None:
            return ""

        chars_per_page = 500
        lower = (page - 1) * chars_per_page
        upper = lower + chars_per_page
        return body.text[lower : lower + upper]

    def step(self) -> dict[str, str | dict[HttpUrl, LinkData]]:

        url = self.location()

        self.follow(url)

        content = ""
        page = 1
        paged = "..."
        while any(paged) and page < 5:
            paged = self.collect_text(page)
            content += paged
            page += 1

        links = self.collect_links()
        return {"page_content": content, "links": links}


walker = Walker.create()


@mcp.tool()
def proceed(estimations: dict[HttpUrl, LinkData] | None = None):
    """primary MCP tool, Agent calls this tool to allow browser automation to continue with its own loop"""
    walker.estimated(estimations)

    return walker.step()


@mcp.tool()
def report(url: str) -> None:
    print(url)


@mcp.resource("context://{target}")
def current_context(target: str) -> dict:
    if "current" == target:
        return {
            "selenium_was_started": walker.driver is not None,
            "selenium_has_page": walker.driver is not None
            and walker.driver.current_url is not None,
            "schema_was_found": False,
        }

    return {}


@mcp.resource("credentials://{name}")
def get_credentials(name: str) -> dict:
    if "example" != name:
        raise Exception("Credentials not found!")

    # @note dummy data for the example
    a_usr, a_pwd = ("test", "test")

    # some credential-obtaining code in between

    return {"username": a_usr, "password": a_pwd}


@mcp.prompt()
def on_failure(ex: str):
    if "ValidationError" in ex:
        return f"Got a validation error, this means you passed in some arguments wrong. Try again with another approach."

    return f"Got a generic exception back ({ex}, this usually means an error that has nothing to do with you had happened. Take a different approach to whatever you were doing."


@mcp.prompt()
def queried_tools(result: str):
    return "You now have a listing of available tools. There should be no need to query again for some time."


@mcp.prompt()
def called_tool(result: str):
    if "validation" in result.lower():
        return f"A validation error was found in tool_call result, it likely means the arguments were wrong. {result}"

    if "error" in result:
        return f"An error was found in tool_call, this would mean it was called wrong: {result}"

    return f"No errors found in tool_call result"


@mcp.prompt()
def try_feed(feed: str) -> str:
    """a formulaic instruction the agent can use to communicate with other LLMs"""
    return f"""You are a helpful assistant, your assignment is to parse given feeds.
    Respond with _only_ a JSON document with the following structure (sample uses dollar sign to signify variable data):
    {
      "agent": "try_feed",
      "result": $resultDataHere
    }
    """


if __name__ == "__main__":
    mcp.run()
