"""Playwright automation for SAP Fiori time entry submission."""

# TODO: Once you have your SAP Fiori URL and can inspect the page, update the
#       placeholder selectors below to match the actual field IDs / labels.
#       Run `timelog init` first to verify your SAP_URL is reachable.

from pathlib import Path

from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PWTimeout

from .config import SAP_PASSWORD, SAP_URL, SAP_USERNAME
from .models import TimeEntry

_SCREENSHOT_DIR = Path("sap_screenshots")

# ---------------------------------------------------------------------------
# TODO: Replace these placeholder selectors with real ones from your SAP Fiori.
#       Inspect the form at SAP_URL to find the correct locators.
# ---------------------------------------------------------------------------
_SEL_USERNAME = "#USERNAME_FIELD-inner"       # TODO: verify
_SEL_PASSWORD = "#PASSWORD_FIELD-inner"       # TODO: verify
_SEL_LOGIN_BTN = "#LOGIN_LINK"               # TODO: verify
_SEL_TIME_ENTRY_TILE = "text=My Timesheet"   # TODO: verify tile / app name
_SEL_ADD_ROW_BTN = "text=Add Row"            # TODO: verify
_SEL_ACTIVITY_INPUT = "[placeholder*='Activity']"  # TODO: verify
_SEL_ACCOUNT_INPUT = "[placeholder*='Account']"    # TODO: verify
_SEL_HOURS_INPUT = "[placeholder*='Hours']"        # TODO: verify
_SEL_SAVE_BTN = "text=Save"                        # TODO: verify
# ---------------------------------------------------------------------------

_TIMEOUT = 30_000  # ms — SAP Fiori can be slow


async def _login(page: Page) -> None:
    """Log in if the login form is present."""
    try:
        await page.wait_for_selector(_SEL_USERNAME, timeout=5_000)
    except PWTimeout:
        return  # Already logged in

    password = SAP_PASSWORD or input("SAP password: ")
    await page.fill(_SEL_USERNAME, SAP_USERNAME)
    await page.fill(_SEL_PASSWORD, password)
    await page.click(_SEL_LOGIN_BTN)
    await page.wait_for_load_state("networkidle", timeout=_TIMEOUT)


async def _fill_entry(page: Page, entry: TimeEntry, index: int) -> None:
    """Fill a single time-entry row on the timesheet form."""
    # TODO: The row-creation and field-filling logic depends on your SAP Fiori
    #       layout. Adjust selectors and interaction sequence accordingly.
    await page.click(_SEL_ADD_ROW_BTN)
    await page.wait_for_timeout(1_000)

    rows = await page.query_selector_all("tr.sapUiTableTr")  # TODO: verify row selector
    row = rows[index] if index < len(rows) else rows[-1]

    activity_field = await row.query_selector(_SEL_ACTIVITY_INPUT)
    account_field = await row.query_selector(_SEL_ACCOUNT_INPUT)
    hours_field = await row.query_selector(_SEL_HOURS_INPUT)

    if activity_field:
        await activity_field.fill(entry.activity_code)
    if account_field:
        await account_field.fill(entry.account_code)
    if hours_field:
        await hours_field.fill(str(entry.hours))


async def submit_entries(entries: list[TimeEntry], headless: bool = False) -> None:
    """Launch Chromium, navigate to SAP Fiori, and submit all *entries*."""
    if not SAP_URL:
        raise ValueError("SAP_URL is not configured. Check your .env file.")

    _SCREENSHOT_DIR.mkdir(exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(SAP_URL, timeout=_TIMEOUT)
            await _login(page)

            # Navigate to timesheet app
            await page.click(_SEL_TIME_ENTRY_TILE, timeout=_TIMEOUT)
            await page.wait_for_load_state("networkidle", timeout=_TIMEOUT)

            for i, entry in enumerate(entries):
                try:
                    await _fill_entry(page, entry, i)
                except Exception as exc:
                    screenshot = _SCREENSHOT_DIR / f"error_entry_{i}.png"
                    await page.screenshot(path=str(screenshot))
                    raise RuntimeError(
                        f"Failed on entry {i} ({entry.event.subject}). "
                        f"Screenshot saved to {screenshot}"
                    ) from exc

            await page.click(_SEL_SAVE_BTN, timeout=_TIMEOUT)
            await page.wait_for_load_state("networkidle", timeout=_TIMEOUT)

        except Exception:
            screenshot = _SCREENSHOT_DIR / "error_final.png"
            await page.screenshot(path=str(screenshot))
            raise
        finally:
            await browser.close()
