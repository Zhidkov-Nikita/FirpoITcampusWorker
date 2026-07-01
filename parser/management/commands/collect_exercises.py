import asyncio
import logging
import os
import sys
from typing import Any
from dotenv import load_dotenv
load_dotenv()

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from playwright.async_api import async_playwright, Browser, Page, Response

from parser.models import ExerciseRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

BASE_URL = "https://edu.firpo.ru"
LOGIN_URL = f"{BASE_URL}/campus"
EXERCISES_URL = f"{BASE_URL}/campus/operator/exercises"
API_QUERY_URL = f"{BASE_URL}/api/query.php"

REQUIRED_KEYS = {"exerciseTitle", "taskTitle", "userName"}

LOGIN_SELECTOR = "input[aria-label='Электронная почта']"
PASSWORD_SELECTOR = "input[aria-label='Пароль']"
SUBMIT_SELECTOR = "button.login-button"


def _load_credentials() -> tuple[str, str]:
    login = os.getenv("FIRPO_LOGIN", "admin")
    password = os.getenv("FIRPO_PASSWORD", "admin")
    if not login or not password:
        raise ValueError(
            "Environment variables FIRPO_LOGIN and FIRPO_PASSWORD must be set"
        )
    return login, password


def _describe_keys(data: object) -> str:
    if not isinstance(data, dict):
        return f"type={type(data).__name__} (not a dict)"
    present = set(data.keys())
    missing = REQUIRED_KEYS - present
    parts = [f"keys={len(present)}"]
    if missing:
        parts.append(f"missing={missing}")
    else:
        parts.append("ALL REQUIRED OK")
    return " | ".join(parts)


def _find_all_valid(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for i, item in enumerate(reversed(responses)):
        idx = len(responses) - 1 - i
        desc = _describe_keys(item)
        if isinstance(item, dict) and REQUIRED_KEYS.issubset(item.keys()):
            valid.append(item)
            logger.info(
                "  [#%d] VALID   — %s | exerciseTitle=%s  taskTitle=%s  userName=%s",
                idx, desc,
                item.get("exerciseTitle", "")[:40],
                item.get("taskTitle", "")[:40],
                item.get("userName", "")[:40],
            )
        else:
            present_keys = sorted(item.keys()) if isinstance(item, dict) else []
            logger.info(
                "  [#%d] SKIPPED — %s | present_keys=%s",
                idx, desc, present_keys[:20],
            )
    valid.reverse()
    return valid


async def collect_exercises_data(headless: bool = True) -> int:
    login, password = _load_credentials()

    captured_responses: list[dict[str, Any]] = []

    async def _on_response(response: Response) -> None:
        if (
            response.request.method == "POST"
            and API_QUERY_URL in response.url
        ):
            try:
                body: Any = await response.json()
                if isinstance(body, list):
                    captured_responses.extend(body)
                    logger.info("Captured list with %d records", len(body))
                elif isinstance(body, dict):
                    captured_responses.append(body)
                    logger.info("Captured single dict response")
            except Exception as exc:
                logger.warning("Failed to parse response JSON: %s", exc)

    def handle_response(response: Response) -> None:
        asyncio.ensure_future(_on_response(response))

    browser: Browser | None = None
    try:
        logger.info("─" * 60)
        logger.info("STEP 1/6: Launching browser")
        logger.info("─" * 60)
        async with async_playwright() as pw:
            logger.info("  Launching Chromium (headless=%s) ...", headless)
            browser = await pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            logger.info("  Browser PID: %s", getattr(browser, "pid", "N/A") if browser else "N/A")

            logger.info("  Creating new page (1920x1080) ...")
            page: Page = await browser.new_page(
                viewport={"width": 1920, "height": 1080}
            )
            page.on("response", handle_response)
            logger.info("  Response interceptor attached")

            logger.info("─" * 60)
            logger.info("STEP 2/6: Logging in")
            logger.info("─" * 60)
            logger.info("  Navigating to %s", LOGIN_URL)
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
            logger.info("  Page loaded, waiting for login form ...")
            await page.wait_for_selector(LOGIN_SELECTOR, timeout=10000)
            logger.info("  Login form found, filling credentials ...")

            await page.fill(LOGIN_SELECTOR, login)
            logger.info("    login field filled")
            await page.fill(PASSWORD_SELECTOR, password)
            logger.info("    password field filled")

            logger.info("  Clicking submit button ...")
            await page.click(SUBMIT_SELECTOR)

            logger.info("  Waiting for redirect to /operator/courses ...")
            await page.wait_for_url("**/operator/courses**", timeout=30000)
            logger.info("  Login successful! Current URL: %s", page.url)

            logger.info("─" * 60)
            logger.info("STEP 3/6: Navigating to exercises page")
            logger.info("─" * 60)
            logger.info("  Going to %s", EXERCISES_URL)
            await page.goto(EXERCISES_URL, wait_until="networkidle", timeout=30000)
            logger.info("  Exercises page loaded. URL: %s", page.url)

            logger.info("─" * 60)
            logger.info("STEP 4/6: Waiting for API responses (5s)")
            logger.info("─" * 60)
            logger.info("  Waiting 5 seconds for AJAX requests to settle ...")
            await asyncio.sleep(5)

            total_captured = len(captured_responses)
            logger.info("  Done! Captured %d individual record(s) from query.php", total_captured)

            if not captured_responses:
                raise RuntimeError(
                    f"No POST responses captured from {API_QUERY_URL}"
                )

            logger.info("─" * 60)
            logger.info("STEP 5/6: Collecting all valid records")
            logger.info("─" * 60)
            logger.info(
                "  Scanning all %d captured records (reverse order)",
                total_captured,
            )
            logger.info("  Looking for records with keys: %s", REQUIRED_KEYS)
            logger.info("─" * 70)

            valid_records = _find_all_valid(captured_responses)
            valid_count = len(valid_records)

            if valid_count == 0:
                logger.info("─" * 70)
                raise RuntimeError(
                    f"No valid record found among all {total_captured} responses "
                    f"- none contained all required keys: {REQUIRED_KEYS}"
                )

            logger.info("─" * 70)
            logger.info("STEP 6/6: Saving %d valid record(s) to database", valid_count)
            logger.info("─" * 60)

            saved_count = 0
            for idx, record_data in enumerate(valid_records, 1):
                try:
                    record = await sync_to_async(ExerciseRecord.from_api_response)(record_data)
                    await sync_to_async(record.save)()
                    saved_count += 1
                    logger.info(
                        "  [%d/%d] ✓ %s — %s (score=%s)",
                        idx, valid_count,
                        record.user_name,
                        record.task_title,
                        record.result_score,
                    )
                except IntegrityError:
                    logger.info(
                        "  [%d/%d] – %s — %s (already exists, skipped)",
                        idx, valid_count,
                        record_data.get("userName", "?"),
                        record_data.get("taskTitle", "?"),
                    )
                except Exception as exc:
                    logger.warning(
                        "  [%d/%d] ✗ Failed to save record #%s: %s",
                        idx, valid_count,
                        record_data.get("id", "?"),
                        exc,
                    )

            logger.info("─" * 60)
            logger.info(
                "  Done! %d of %d valid record(s) saved to database",
                saved_count,
                valid_count,
            )
            logger.info("─" * 60)
            return saved_count

    except Exception:
        logger.exception("✗ Exercise collection failed")
        raise
    finally:
        if browser is not None:
            logger.info("  Closing browser ...")
            await browser.close()
            logger.info("  Browser closed")
        logger.info("─" * 60)


class Command(BaseCommand):
    help = "Collect exercises JSON from edu.firpo.ru via Playwright"

    def add_arguments(self, parser):
        parser.add_argument(
            "--headless",
            action="store_true",
            default=True,
            help="Run browser in headless mode (default: True)",
        )
        parser.add_argument(
            "--no-headless",
            action="store_false",
            dest="headless",
            help="Run browser in visible mode (for debugging)",
        )

    def handle(self, *args, **options):
        try:
            saved_count = asyncio.run(collect_exercises_data(headless=options["headless"]))
            self.stdout.write(self.style.SUCCESS(f"Saved {saved_count} exercise record(s)"))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Exercise collection failed")
            raise CommandError(f"Unexpected error: {exc}") from exc
