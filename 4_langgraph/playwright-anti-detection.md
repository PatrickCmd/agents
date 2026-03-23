# Bypassing Bot Detection with Playwright + LangChain

Many websites (Google, CNN, etc.) detect automated browsers and serve CAPTCHAs or block access. Below are practical approaches to mitigate this, ranging from easiest to most involved.

## Why It Happens

Playwright launches Chromium with telltale automation flags. Websites detect this via:

- `navigator.webdriver` being `true`
- Missing browser plugins/features that real browsers have
- Specific HTTP headers and fingerprints
- Unusual browsing patterns (instant navigation, no mouse movement)

---

## Solution 1: Use `playwright-stealth`

The `playwright-stealth` package patches known detection vectors.

```bash
pip install playwright-stealth
```

```python
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

pw = await async_playwright().start()
browser = await pw.chromium.launch(headless=False)
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
page = await context.new_page()
await stealth_async(page)

toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
tools = toolkit.get_tools()
```

**Caveat:** The LangChain toolkit creates its own pages via `aget_current_page()`, so stealth only applies to pages you create directly. For full coverage you'd need to apply stealth to every new page the toolkit creates, which requires a custom wrapper.

---

## Solution 2: Set a Realistic User Agent and Viewport

The default Playwright user agent screams "bot." Override it when creating the browser context:

```python
from playwright.async_api import async_playwright
import nest_asyncio
nest_asyncio.apply()

pw = await async_playwright().start()
browser = await pw.chromium.launch(headless=False)
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    viewport={"width": 1920, "height": 1080},
    locale="en-US",
    timezone_id="America/New_York",
)
context.set_default_navigation_timeout(120000)

toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
tools = toolkit.get_tools()
```

This replaces `create_async_playwright_browser()` since that utility function doesn't expose context options.

---

## Solution 3: Use a Search API Instead of Navigating to Google

Google aggressively blocks bots. Use an API-based search tool alongside Playwright:

```python
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import Tool

search = GoogleSerperAPIWrapper()
tool_search = Tool(
    name="web_search",
    func=search.run,
    description="Search the web for information. Use this instead of navigating to google.com"
)

all_tools = tools + [tool_search]
```

The agent uses the Serper API for searching (no CAPTCHA) and Playwright only for visiting specific target pages.

---

## Solution 4: Launch with Extra Chromium Args

```python
browser = await pw.chromium.launch(
    headless=False,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
)
```

`--disable-blink-features=AutomationControlled` prevents Chromium from setting `navigator.webdriver = true`, one of the primary detection signals.

---

## Solution 5: Use a Persistent Browser Profile

A fresh browser with zero cookies and history is a strong bot signal. A persistent profile looks more like a real user:

```python
context = await browser.new_context(
    storage_state="browser_state.json"  # load saved cookies/local storage
)

# After browsing, save the state for next time:
# await context.storage_state(path="browser_state.json")
```

---

## Recommended Combination

Combine **Solution 2 + Solution 3**:

1. Set a realistic user agent and viewport on the browser.
2. Add a search API tool so the agent doesn't navigate to Google at all.

This way:

- The agent uses the Serper API for searching (no CAPTCHA possible).
- The agent uses Playwright only for visiting specific target pages (lower detection risk).
- The browser looks more realistic with a proper user agent and viewport.
