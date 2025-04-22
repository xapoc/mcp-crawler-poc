from mcp.server.fastmcp import FastMCP

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options

driver = None


def drive():
    options = Options()
    # options.add_argument("--headless")

    options.set_preference(
        "general.useragent.override",
        "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0",
    )
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("javascript.enabled", False)

    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(60)


mcp = FastMCP("OpenAPI Seeker", log_level="ERROR")


@mcp.tool()
def get_greeted(name: str) -> str:
    return f"Greetings from mcp tool, {name}!"


@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    return f"Hello {name}"


@mcp.prompt()
def on_greeter_prompt(message: str) -> str:
    return f"Summarize the following message please: {message}"


if __name__ == "__main__":
    mcp.run()
