import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional
from dotenv import load_dotenv
load_dotenv()
from django.core.management.base import BaseCommand, CommandError
from playwright.async_api import async_playwright, Browser, Page, Response

logger = logging.getLogger(__name__)

BASE_URL = "https://edu.firpo.ru"
LOGIN_URL = f"{BASE_URL}/campus"
EXERCISES_URL = f"{BASE_URL}/campus/operator/exercises"
API_QUERY_URL = f"{BASE_URL}/api/query.php"

OUTPUT_DIR = "php"

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


def _build_filename() -> str:
    now = datetime.now()
    timestamp = now.strftime("%d%m%y%H%M")
    return f"{timestamp}.json"


def _save_json(data: dict[str, Any], filename: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath


async def collect_exercises_data(headless: bool = True) -> str:
    login, password = _load_credentials()

    captured_response: Optional[dict[str, Any]] = None

    async def _on_response(response: Response) -> None:
        nonlocal captured_response
        if (
            response.request.method == "POST"
            and API_QUERY_URL in response.url
        ):
            try:
                body: dict[str, Any] = await response.json()
                captured_response = body
                logger.info("Captured POST response from %s", response.url)
            except Exception as exc:
                logger.warning("Failed to parse response JSON: %s", exc)

    def handle_response(response: Response) -> None:
        asyncio.ensure_future(_on_response(response))

    browser: Optional[Browser] = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )

            page: Page = await browser.new_page(
                viewport={"width": 1920, "height": 1080}
            )
            page.on("response", handle_response)

            logger.info("Navigating to login page: %s", LOGIN_URL)
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_selector(LOGIN_SELECTOR, timeout=10000)

            await page.fill(LOGIN_SELECTOR, login)
            await page.fill(PASSWORD_SELECTOR, password)

            logger.info("Submitting login form")
            await page.click(SUBMIT_SELECTOR)

            await page.wait_for_url("**/operator/courses**", timeout=30000)
            logger.info("Login successful, redirected to /operator/courses")

            logger.info("Navigating to exercises page: %s", EXERCISES_URL)
            await page.goto(EXERCISES_URL, wait_until="networkidle", timeout=30000)

            logger.info("Waiting 5 seconds for API requests to settle")
            await asyncio.sleep(5)

            if captured_response is None:
                raise RuntimeError(
                    f"No POST response captured from {API_QUERY_URL}"
                )

            filename = _build_filename()
            filepath = _save_json(captured_response, filename)
            logger.info("Response saved to %s", filepath)
            return filepath

    except Exception:
        logger.exception("Exercise collection failed")
        raise
    finally:
        if browser is not None:
            await browser.close()
            logger.info("Browser closed")


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
            filepath = asyncio.run(collect_exercises_data(headless=options["headless"]))
            self.stdout.write(self.style.SUCCESS(f"Exercises data saved to {filepath}"))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            logger.exception("Exercise collection failed")
            raise CommandError(f"Unexpected error: {exc}") from exc
