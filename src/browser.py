from playwright.sync_api import sync_playwright

from src.config import G2B_SHOP_URL


def launch_available_browser(playwright):
    """
    Playwright 내장 Chromium이 아니라
    PC에 설치된 Microsoft Edge 또는 Chrome을 우선 사용한다.

    exe 배포 시 Playwright Chromium 브라우저 누락 문제를 피하기 위한 방식.
    """

    browser_options = {
        "headless": False,
        "slow_mo": 300
    }

    # 1순위: Microsoft Edge
    try:
        print("Microsoft Edge 브라우저 실행 시도")
        return playwright.chromium.launch(
            channel="msedge",
            **browser_options
        )
    except Exception as error:
        print(f"Microsoft Edge 실행 실패: {error}")

    # 2순위: Google Chrome
    try:
        print("Google Chrome 브라우저 실행 시도")
        return playwright.chromium.launch(
            channel="chrome",
            **browser_options
        )
    except Exception as error:
        print(f"Google Chrome 실행 실패: {error}")

    # 3순위: Playwright Chromium
    # 개발 PC에서는 playwright install chromium이 되어 있으면 실행 가능
    try:
        print("Playwright Chromium 실행 시도")
        return playwright.chromium.launch(
            **browser_options
        )
    except Exception as error:
        print(f"Playwright Chromium 실행 실패: {error}")

    raise Exception(
        "실행 가능한 브라우저를 찾지 못했습니다. "
        "Microsoft Edge 또는 Google Chrome이 설치되어 있는지 확인하세요."
    )


def open_browser():
    """
    Playwright 브라우저를 실행하고 나라장터 종합쇼핑몰에 접속한다.
    """

    playwright = sync_playwright().start()

    browser = launch_available_browser(playwright)

    context = browser.new_context()

    page = context.new_page()

    page.goto(
        G2B_SHOP_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    return playwright, browser, context, page


def close_browser(playwright, browser, context):
    """
    브라우저와 Playwright를 종료한다.
    """

    try:
        context.close()
    except Exception:
        pass

    try:
        browser.close()
    except Exception:
        pass

    try:
        playwright.stop()
    except Exception:
        pass