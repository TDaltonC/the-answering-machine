import asyncio
import os
import re

from browser_use import Agent, Browser
from browser_use.llm import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()

SFPL_USERNAME = os.environ["SFPL_USERNAME"]
SFPL_PASSWORD = os.environ["SFPL_PASSWORD"]


def load_holds_md() -> str:
    with open("holds.md") as f:
        return f.read()


def build_task() -> str:
    return f"""\
You need to log into the San Francisco Public Library website and check the status of my holds.

## STEP 1 — Log in
Go to https://sfpl.org and log in:
- Click "Log In" in the top navigation
- Username/Barcode: {SFPL_USERNAME}
- Password/PIN: {SFPL_PASSWORD}
- After logging in, confirm you see your account.
  If login fails, report the error and call "done" immediately.

## STEP 2 — Check hold statuses
Navigate to your holds page (usually under "My Account" → "Holds" or similar).

For each book on hold, note:
- The book title
- The current status (e.g. "On hold", "In transit", "Ready for pickup", "Suspended", etc.)
- The pickup branch

## STEP 3 — Report results (this is the ONLY time you should call "done")
Call "done" with a report in EXACTLY this format, one line per book:

HOLD STATUSES:
- "Title" by Author | Status: <status> | Branch: <branch>
- "Title" by Author | Status: <status> | Branch: <branch>

Use these exact status values: "On hold", "In transit", "Ready for pickup", or whatever
the site shows. Do NOT call "done" until you have checked all holds.
"""


def update_holds_md(agent_result: str) -> None:
    """Parse the agent's status report and update holds.md."""
    # Read existing holds.md to preserve "Why" fields
    existing = {}
    try:
        with open("holds.md") as f:
            for match in re.finditer(
                r'-\s+"([^"]+)"\s+by\s+([^|]+)\|\s*Status:\s*[^|]+\|\s*Branch:\s*[^|]+\|\s*Why:\s*(.+)',
                f.read(),
            ):
                existing[match.group(1).strip().lower()] = match.group(3).strip()
    except FileNotFoundError:
        pass

    # Parse agent results
    lines = ["# Books on Hold"]
    for match in re.finditer(
        r'-\s+"([^"]+)"\s+by\s+([^|]+)\|\s*Status:\s*([^|]+)\|\s*Branch:\s*([^|\n]+)',
        agent_result,
    ):
        title = match.group(1).strip()
        author = match.group(2).strip()
        status = match.group(3).strip()
        branch = match.group(4).strip()
        why = existing.get(title.lower(), "")
        lines.append(
            f'- "{title}" by {author} | Status: {status} | Branch: {branch} | Why: {why}'
        )

    if len(lines) > 1:
        with open("holds.md", "w") as f:
            f.write("\n".join(lines) + "\n")
        print("\nholds.md updated with current statuses")
    else:
        print("\nWarning: could not parse hold statuses from agent result")
        print("Raw result:", agent_result)


async def main():
    task = build_task()

    browser = Browser()
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

    agent = Agent(task=task, llm=llm, browser=browser)
    result = await agent.run()

    agent_text = result.final_result()
    print(agent_text)
    update_holds_md(agent_text)


if __name__ == "__main__":
    asyncio.run(main())
