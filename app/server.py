import random
import time

from mcp.server.fastmcp import FastMCP

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options


driver = None
mcp = FastMCP("OpenAPI Seeker")  # , log_level="ERROR")


@mcp.tool()
def selenium_start():
    global driver

    if driver is not None:
        return "ALREADY RUNNING"

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
    return "STARTED"


@mcp.tool()
def selenium_stop():
    global driver

    driver.quit()


@mcp.tool()
def selenium_follow_link(url: str) -> bool:
    global driver

    driver.get(url)
    time.sleep(random.randint(0, 30))


@mcp.tool()
def selenium_collect_links() -> dict[str, str]:
    global driver

    links = {}

    for e in driver.find_elements(By.CSS_SELECTOR, "a"):
        links[e.text] = e.get_attribute("href")

    return links


@mcp.tool()
def selenium_collect_text(page: int = 1) -> str:
    global driver

    body = driver.find_element(By.CSS_SELECTOR, "body")
    if body is None:
        return "blank page"

    text = body.text
    chars_per_page = 500

    lower = (page - 1) * chars_per_page
    upper = lower + chars_per_page
    return text[lower : lower + upper]


@mcp.tool()
def report(url: str) -> None:
    print(url)


@mcp.resource("context://{target}")
def current_context(target: str) -> dict:
    if "current" == target:
        global driver

        return {
            "selenium_was_started": driver is not None,
            "selenium_has_page": driver is not None and driver.current_url is not None,
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
