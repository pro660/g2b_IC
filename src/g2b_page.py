import re
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.config import LOG_DIR, G2B_SHOP_URL


def close_extra_popup_pages(page):
    """
    새 창 또는 새 탭 형태로 열린 팝업 페이지를 닫는다.
    메인 page는 닫지 않는다.
    """

    context = page.context

    for popup_page in context.pages:
        if popup_page == page:
            continue

        try:
            if not popup_page.is_closed():
                print(f"추가 팝업 페이지 닫기: {popup_page.url}")
                popup_page.close()
        except Exception:
            pass


def click_visible_first(locator, label="", timeout=1000):
    """
    locator에 해당하는 요소들 중 화면에 보이는 첫 번째 요소를 클릭한다.
    클릭 성공 시 True, 실패 시 False 반환.
    """

    try:
        count = locator.count()
    except Exception:
        return False

    for index in range(count):
        try:
            target = locator.nth(index)

            if target.is_visible(timeout=timeout):
                target.click(timeout=timeout)

                if label:
                    print(f"팝업 닫기 클릭: {label}")

                return True

        except Exception:
            continue

    return False


def close_all_popups(page, max_rounds=8):
    """
    나라장터 접속 시 뜨는 팝업을 최대한 안전하게 닫는다.

    주의:
    이 함수는 검색창을 열기 전에만 호출하는 것이 안전하다.
    검색창을 연 뒤 호출하면 검색창 레이어까지 닫아버릴 수 있다.
    """

    print("팝업 확인 중...")

    total_closed = 0

    for _ in range(max_rounds):
        closed_this_round = False

        close_extra_popup_pages(page)

        close_candidates = [
            (
                page.get_by_role(
                    "button",
                    name=re.compile(r"창닫기|닫기버튼|close", re.IGNORECASE)
                ),
                "button role 창닫기"
            ),
            (
                page.locator("button:has-text('창닫기')"),
                "button 창닫기"
            ),
            (
                page.locator("a:has-text('창닫기')"),
                "a 창닫기"
            ),
            (
                page.locator("input[type='button'][value*='창닫기']"),
                "input 창닫기"
            ),
            (
                page.locator("text=오늘 하루 보지 않기"),
                "오늘 하루 보지 않기"
            ),
            (
                page.locator("text=오늘 하루 열지 않기"),
                "오늘 하루 열지 않기"
            ),
            (
                page.locator("text=오늘 하루 닫기"),
                "오늘 하루 닫기"
            ),
        ]

        for locator, label in close_candidates:
            if click_visible_first(locator, label=label):
                total_closed += 1
                closed_this_round = True
                page.wait_for_timeout(500)
                break

        if not closed_this_round:
            break

    if total_closed == 0:
        print("닫을 팝업 없음")
    else:
        print(f"팝업 닫기 완료: {total_closed}개")


def find_visible_first(page, locators, timeout=2000):
    """
    locator 후보들 중 화면에 보이는 첫 번째 요소를 찾는다.
    """

    last_error = None

    for locator, label in locators:
        try:
            count = locator.count()

            if count == 0:
                continue

            for index in range(count):
                target = locator.nth(index)

                if target.is_visible(timeout=timeout):
                    print(f"요소 찾기 성공: {label}")
                    return target

        except Exception as error:
            last_error = error
            continue

    raise Exception(f"화면에 보이는 요소를 찾지 못했습니다. 마지막 오류: {last_error}")


def open_main_search_box(page):
    """
    상단 통합검색 버튼을 클릭해서 검색창을 연다.
    """

    search_button_candidates = [
        (
            page.locator("#mf_wfm_gnb_wfm_gnbBtm_btnMtSrch"),
            "상단 통합검색 버튼 ID"
        ),
        (
            page.get_by_role("button", name="검색"),
            "role 검색 버튼"
        ),
        (
            page.locator("button:has-text('검색')"),
            "button 검색"
        ),
        (
            page.locator("a:has-text('검색')"),
            "a 검색"
        ),
        (
            page.get_by_text("검색", exact=True),
            "text 검색"
        ),
    ]

    target = find_visible_first(page, search_button_candidates)
    target.click(timeout=5000)

    page.wait_for_timeout(1000)

    print("상단 검색 버튼 클릭 완료")


def find_search_input(page):
    """
    검색어 입력창을 찾는다.
    codegen에서 나온 textbox를 우선 사용하고,
    실패하면 다른 input 후보를 순서대로 찾는다.
    """

    input_candidates = [
        (
            page.get_by_role("textbox", name="검색어를 입력하세요"),
            "role textbox 검색어를 입력하세요"
        ),
        (
            page.locator("input[placeholder='검색어를 입력하세요']"),
            "placeholder 정확히 일치"
        ),
        (
            page.locator("input[placeholder*='검색어']"),
            "placeholder 검색어 포함"
        ),
        (
            page.locator("input[title*='검색어']"),
            "title 검색어 포함"
        ),
        (
            page.locator("input[id*='Srch']"),
            "id Srch 포함"
        ),
        (
            page.locator("input[id*='srch']"),
            "id srch 포함"
        ),
        (
            page.locator("input[id*='Search']"),
            "id Search 포함"
        ),
        (
            page.locator("input[id*='search']"),
            "id search 포함"
        ),
        (
            page.locator("input[type='text']"),
            "input text"
        ),
    ]

    return find_visible_first(page, input_candidates)


def search_by_item_number(page, item_number):
    """
    나라장터 종합쇼핑몰에서 물품식별번호를 검색한다.
    """

    item_number = str(item_number).strip()

    if not item_number:
        raise ValueError("물품식별번호가 비어 있습니다.")

    print(f"검색 시도: {item_number}")

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)

    close_all_popups(page)

    open_main_search_box(page)

    try:
        search_input = find_search_input(page)

        search_input.click(timeout=5000)
        search_input.fill(item_number)
        page.wait_for_timeout(300)
        search_input.press("Enter")

    except PlaywrightTimeoutError:
        raise Exception("검색어 입력창을 찾지 못했습니다.")

    except Exception as error:
        raise Exception(f"검색어 입력 또는 Enter 실행 실패: {error}")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(3000)

    print(f"검색 완료: {item_number}")


def find_product_click_target(page, item_number):
    """
    검색 결과 화면에서 물품식별번호가 포함된 결과를 찾아 클릭 대상 요소와 상세링크 후보를 반환한다.

    반환:
    - 클릭할 locator
    - 상세페이지 링크 후보
    """

    item_number = str(item_number).strip()

    print(f"검색 결과에서 물품 찾기: {item_number}")

    page.wait_for_timeout(1500)

    row_candidates = [
        (
            page.locator("tr").filter(has_text=item_number),
            "tr 행"
        ),
        (
            page.locator("li").filter(has_text=item_number),
            "li 항목"
        ),
        (
            page.locator("div").filter(has_text=item_number),
            "div 영역"
        ),
    ]

    for locator, label in row_candidates:
        try:
            count = locator.count()

            if count == 0:
                continue

            for index in range(count):
                row = locator.nth(index)

                if not row.is_visible(timeout=1000):
                    continue

                print(f"검색 결과 영역 찾기 성공: {label}")

                clickable_candidates = [
                    (
                        row.locator("a"),
                        "결과 영역 내부 a"
                    ),
                    (
                        row.locator("button"),
                        "결과 영역 내부 button"
                    ),
                    (
                        row.locator("[role='button']"),
                        "결과 영역 내부 role button"
                    ),
                    (
                        row.locator("[onclick]"),
                        "결과 영역 내부 onclick"
                    ),
                ]

                for clickable_locator, clickable_label in clickable_candidates:
                    try:
                        clickable_count = clickable_locator.count()

                        if clickable_count == 0:
                            continue

                        for clickable_index in range(clickable_count):
                            clickable = clickable_locator.nth(clickable_index)

                            if clickable.is_visible(timeout=1000):
                                print(f"클릭 대상 찾기 성공: {clickable_label}")

                                detail_link = extract_detail_link_from_locator(page, clickable)

                                if detail_link:
                                    print(f"상세링크 후보 추출 성공: {detail_link}")
                                else:
                                    print("클릭 대상에서 상세링크 후보를 찾지 못했습니다.")

                                return clickable, detail_link

                    except Exception:
                        continue

                # 내부 클릭 요소가 없으면 행 자체를 클릭 대상으로 사용
                print("내부 클릭 요소가 없어 결과 행 자체를 클릭합니다.")

                detail_link = extract_detail_link_from_locator(page, row)

                if detail_link:
                    print(f"상세링크 후보 추출 성공: {detail_link}")
                else:
                    print("결과 행에서 상세링크 후보를 찾지 못했습니다.")

                return row, detail_link

        except Exception:
            continue

    text_candidates = [
        (
            page.get_by_text(item_number, exact=True),
            "물품식별번호 exact text"
        ),
        (
            page.locator(f"text={item_number}"),
            "물품식별번호 text locator"
        ),
    ]

    target = find_visible_first(page, text_candidates, timeout=2000)
    detail_link = extract_detail_link_from_locator(page, target)

    return target, detail_link


def click_target_and_get_detail_page(page, target):
    """
    검색 결과 클릭 후 상세페이지를 반환한다.

    경우 1. 새 창/새 탭이 열림
    경우 2. 현재 페이지에서 상세페이지로 이동
    둘 다 처리한다.
    """

    context = page.context
    before_pages = list(context.pages)
    before_url = page.url

    target.scroll_into_view_if_needed()
    target.click(timeout=5000)

    page.wait_for_timeout(3000)

    after_pages = list(context.pages)

    new_pages = []

    for candidate_page in after_pages:
        if candidate_page not in before_pages:
            new_pages.append(candidate_page)

    if new_pages:
        detail_page = new_pages[-1]
        detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
        detail_page.wait_for_timeout(1000)

        print(f"상세페이지 새 창 감지: {detail_page.url}")
        return detail_page

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(1000)

    after_url = page.url

    if before_url != after_url:
        print(f"현재 페이지에서 상세페이지 이동 감지: {after_url}")
    else:
        print("URL 변화는 없지만 현재 페이지를 상세페이지 후보로 사용합니다.")

    return page


def open_product_detail_from_search_result(page, item_number):
    """
    검색 결과에서 해당 물품을 클릭하여 상세페이지로 진입한다.

    반환:
    - detail_page
    - detail_link
    """

    target, detail_link = find_product_click_target(page, item_number)
    detail_page = click_target_and_get_detail_page(page, target)

    # 검색 결과에서 링크를 못 찾은 경우 fallback으로 현재 URL 사용
    if not detail_link:
        detail_link = detail_page.url

    print(f"상세페이지 진입 완료: {detail_page.url}")
    print(f"저장할 상세페이지 링크: {detail_link}")

    return detail_page, detail_link


def clean_text(text):
    """
    화면에서 가져온 텍스트를 엑셀에 저장하기 좋게 정리한다.
    """

    if text is None:
        return ""

    text = str(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()

def normalize_detail_link(page, raw_link):
    """
    검색 결과에서 가져온 href, onclick, data-url 값을 실제 링크 형태로 정리한다.
    """

    raw_link = clean_text(raw_link)

    if not raw_link:
        return ""

    # 이미 완전한 URL이면 그대로 사용
    if raw_link.startswith("http://") or raw_link.startswith("https://"):
        return raw_link

    # /path 형태면 현재 사이트 기준으로 절대 URL 변환
    if raw_link.startswith("/"):
        return urljoin(G2B_SHOP_URL, raw_link)

    # ./path 또는 relative path 처리
    if not raw_link.startswith("javascript:") and not raw_link.startswith("#"):
        return urljoin(page.url or G2B_SHOP_URL, raw_link)

    # javascript: 또는 #이면 실제 URL이 아닐 수 있음
    return raw_link


def extract_url_from_onclick(page, onclick_text):
    """
    onclick 안에 URL이 들어있는 경우 추출한다.
    예:
    onclick="goDetail('/detail/path?id=123')"
    """

    onclick_text = clean_text(onclick_text)

    if not onclick_text:
        return ""

    # https://... 직접 포함
    match = re.search(r"https?://[^'\"\s)]+", onclick_text)
    if match:
        return normalize_detail_link(page, match.group(0))

    # '/path/...' 또는 "/path/..." 포함
    match = re.search(r"['\"](\/[^'\"]+)['\"]", onclick_text)
    if match:
        return normalize_detail_link(page, match.group(1))

    return ""


def extract_detail_link_from_locator(page, locator):
    """
    클릭 대상 요소에서 상세페이지 링크 후보를 추출한다.

    우선순위:
    1. 자기 자신의 href
    2. 부모 a 태그의 href
    3. data-url / data-href / data-link
    4. onclick 내부 URL
    """

    # 1. 자기 자신의 href
    try:
        href = locator.get_attribute("href", timeout=1000)
        href = normalize_detail_link(page, href)

        if href and not href.startswith("#") and not href.startswith("javascript:"):
            return href
    except Exception:
        pass

    # 2. 부모 a 태그 href
    try:
        closest_href = locator.evaluate(
            """
            el => {
                const a = el.closest('a');
                if (!a) return '';
                return a.href || a.getAttribute('href') || '';
            }
            """
        )

        closest_href = normalize_detail_link(page, closest_href)

        if closest_href and not closest_href.startswith("#") and not closest_href.startswith("javascript:"):
            return closest_href
    except Exception:
        pass

    # 3. data 계열 속성
    for attr_name in ["data-url", "data-href", "data-link"]:
        try:
            attr_value = locator.get_attribute(attr_name, timeout=1000)
            attr_value = normalize_detail_link(page, attr_value)

            if attr_value:
                return attr_value
        except Exception:
            continue

    # 4. onclick 안의 URL 추출
    try:
        onclick_text = locator.get_attribute("onclick", timeout=1000)
        onclick_url = extract_url_from_onclick(page, onclick_text)

        if onclick_url:
            return onclick_url
    except Exception:
        pass

    return ""

def get_body_text(page):
    """
    상세페이지 전체 텍스트를 가져온다.
    """

    try:
        body_text = page.locator("body").inner_text(timeout=10000)
        return clean_text(body_text)
    except Exception:
        return ""


def save_detail_text_debug(page, item_number):
    """
    상세페이지의 전체 텍스트를 줄 번호와 함께 logs 폴더에 저장한다.
    상품명, 업체명, 구성, 옵션/기타 위치를 확인하기 위한 디버깅용 함수.
    """

    try:
        body_text = page.locator("body").inner_text(timeout=10000)
    except Exception as error:
        body_text = f"상세페이지 텍스트 추출 실패: {error}"

    lines = body_text.splitlines()

    debug_path = LOG_DIR / f"detail_debug_{item_number}.txt"

    with open(debug_path, "w", encoding="utf-8") as file:
        for index, line in enumerate(lines, start=1):
            clean_line = clean_text(line)

            if clean_line:
                file.write(f"{index}: {clean_line}\n")

    print(f"상세페이지 디버그 텍스트 저장 완료: {debug_path}")


def extract_next_line_value(body_text, labels):
    """
    전체 텍스트에서 특정 라벨 다음 줄의 값을 가져온다.

    예:
    물품식별명
    데스크톱컴퓨터
    """

    lines = []

    for line in body_text.splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    for index, line in enumerate(lines):
        for label in labels:
            if line == label:
                if index + 1 < len(lines):
                    return clean_text(lines[index + 1])

            if line.startswith(label):
                value = line.replace(label, "", 1)
                value = value.lstrip(" :：-")
                value = clean_text(value)

                if value:
                    return value

    return ""


def extract_value_from_lines(body_text, label):
    """
    상세페이지 전체 텍스트에서 특정 항목명(label)의 값을 추출한다.

    예시 1:
    구성
    본체 1개, 케이블 1개

    예시 2:
    구성 : 본체 1개, 케이블 1개
    """

    lines = []

    for line in body_text.splitlines():
        line = clean_text(line)

        if line:
            lines.append(line)

    for index, line in enumerate(lines):
        if line.startswith(label):
            value = line.replace(label, "", 1)
            value = value.lstrip(" :：-")
            value = clean_text(value)

            if value:
                return value

            if index + 1 < len(lines):
                next_value = clean_text(lines[index + 1])

                if next_value and next_value != label:
                    return next_value

    return ""


def extract_value_from_table_like_area(page, label):
    """
    table, tr, div 등 화면 구조에서 label이 들어간 영역을 찾아 값을 추출한다.
    나라장터 화면 구조가 동적으로 바뀔 수 있어서 여러 방식으로 시도한다.
    """

    label = str(label).strip()

    row_candidates = [
        page.locator("tr").filter(has_text=label),
        page.locator("li").filter(has_text=label),
        page.locator("div").filter(has_text=label),
    ]

    for locator in row_candidates:
        try:
            count = locator.count()

            if count == 0:
                continue

            for index in range(count):
                row = locator.nth(index)

                if not row.is_visible(timeout=1000):
                    continue

                row_text = clean_text(row.inner_text(timeout=3000))

                if not row_text:
                    continue

                value = row_text.replace(label, "", 1)
                value = value.lstrip(" :：-")
                value = clean_text(value)

                if value and value != label:
                    return value

        except Exception:
            continue

    return ""


def extract_detail_value(page, label):
    """
    상세페이지에서 label에 해당하는 값을 추출한다.

    1차: table/div 구조 기준
    2차: 전체 텍스트 줄 기준
    """

    value = extract_value_from_table_like_area(page, label)

    if value:
        return value

    body_text = get_body_text(page)
    return extract_value_from_lines(body_text, label)


def extract_product_name_precise(page):
    """
    상세페이지에서 상품명을 정확하게 추출한다.

    나라장터 상세페이지에서 상품명은 보통
    <span class="w2textbox prduct_name">상품명</span>
    형태로 들어있다.

    주의:
    class명이 product_name이 아니라 prduct_name이다.
    사이트에서 실제로 이렇게 쓰고 있으므로 그대로 사용한다.
    """

    product_name_candidates = [
        page.locator("span.prduct_name"),
        page.locator(".prduct_name"),
        page.locator("span.w2textbox.prduct_name"),
    ]

    for locator in product_name_candidates:
        try:
            count = locator.count()

            if count == 0:
                continue

            for index in range(count):
                target = locator.nth(index)

                if target.is_visible(timeout=1000):
                    product_name = clean_text(target.inner_text(timeout=3000))

                    if product_name:
                        return product_name

        except Exception:
            continue

    body_text = get_body_text(page)

    product_name_labels = [
        "물품식별명",
        "상품명",
        "제품명",
        "품명",
        "세부품명",
        "세부품명(명칭)",
        "모델명",
        "규격명",
    ]

    product_name = extract_next_line_value(body_text, product_name_labels)

    return product_name


def extract_product_detail_info(page, item_number):
    """
    상세페이지에서 필요한 상품 정보를 추출한다.

    추출 대상:
    - 상품명
    - 업체명
    - 구성
    - 옵션/기타
    """

    print(f"상세정보 추출 시작: {item_number}")

    page.wait_for_timeout(1500)

    save_detail_text_debug(page, item_number)

    detail_url = page.url

    product_name = extract_product_name_precise(page)

    company_name = extract_company_name_precise(page)

    composition = extract_detail_value(page, "구성")

    option_etc = (
        extract_detail_value(page, "옵션/기타")
        or extract_detail_value(page, "옵션")
        or extract_detail_value(page, "기타")
    )

    result = {
        "물품식별번호": str(item_number).strip(),
        "상품명": product_name,
        "업체명": company_name,
        "상세페이지링크": detail_url,
        "구성": composition,
        "옵션/기타": option_etc,
    }

    print("상세정보 추출 결과")
    print(f"- 상품명: {product_name}")
    print(f"- 업체명: {company_name}")
    print(f"- 구성: {composition}")
    print(f"- 옵션/기타: {option_etc}")

    return result

def extract_url_from_text(text):
    """
    텍스트 안에서 http 또는 https로 시작하는 URL을 추출한다.
    """

    text = clean_text(text)

    if not text:
        return ""

    match = re.search(r"https?://[^\s'\"<>]+", text)

    if match:
        return match.group(0)

    return ""


def find_share_button(page):
    """
    상세페이지에서 공유 버튼을 찾는다.
    나라장터 화면 구조가 바뀔 수 있으므로 여러 후보를 순서대로 찾는다.
    """

    share_button_candidates = [
        (
            page.get_by_role(
                "button",
                name=re.compile(r"공유|링크|URL", re.IGNORECASE)
            ),
            "role 공유 버튼"
        ),
        (
            page.locator("button:has-text('공유')"),
            "button 공유"
        ),
        (
            page.locator("a:has-text('공유')"),
            "a 공유"
        ),
        (
            page.locator("[title*='공유']"),
            "title 공유"
        ),
        (
            page.locator("[aria-label*='공유']"),
            "aria-label 공유"
        ),
        (
            page.locator("img[alt*='공유']"),
            "img alt 공유"
        ),
        (
            page.locator("[class*='share']"),
            "class share"
        ),
        (
            page.locator("[id*='share']"),
            "id share"
        ),
        (
            page.locator("[class*='Share']"),
            "class Share"
        ),
        (
            page.locator("[id*='Share']"),
            "id Share"
        ),
    ]

    return find_visible_first(page, share_button_candidates, timeout=2000)


def read_url_from_inputs(page):
    """
    공유창 안의 input 또는 textarea에서 URL을 읽는다.
    """

    input_candidates = [
        page.locator("input"),
        page.locator("textarea"),
    ]

    for locator in input_candidates:
        try:
            count = locator.count()

            for index in range(count):
                target = locator.nth(index)

                try:
                    # input / textarea 값 읽기
                    value = target.input_value(timeout=1000)
                    url = extract_url_from_text(value)

                    if url:
                        return url
                except Exception:
                    pass

                try:
                    # value 속성 직접 읽기
                    value = target.get_attribute("value", timeout=1000)
                    url = extract_url_from_text(value)

                    if url:
                        return url
                except Exception:
                    pass

        except Exception:
            continue

    return ""


def read_url_from_visible_text(page):
    """
    공유창이나 상세페이지의 화면 텍스트에서 URL을 읽는다.
    """

    try:
        body_text = page.locator("body").inner_text(timeout=5000)
        return extract_url_from_text(body_text)
    except Exception:
        return ""


def extract_share_link_from_detail_page(page):
    """
    상세페이지의 공유 버튼을 클릭해서 실제 공유 URL을 추출한다.

    처리 가능한 경우:
    1. 공유 버튼 클릭 후 현재 페이지에 모달이 뜨는 경우
    2. 공유 버튼 클릭 후 새 창/새 탭이 열리는 경우
    3. 공유 URL이 input/textarea에 들어있는 경우
    4. 공유 URL이 그냥 텍스트로 노출되는 경우
    """

    print("공유 링크 추출 시작")

    context = page.context
    before_pages = list(context.pages)

    try:
        share_button = find_share_button(page)
    except Exception as error:
        print(f"공유 버튼을 찾지 못했습니다: {error}")
        return ""

    try:
        share_button.scroll_into_view_if_needed()
        share_button.click(timeout=5000)
    except Exception as error:
        print(f"공유 버튼 클릭 실패: {error}")
        return ""

    page.wait_for_timeout(1500)

    after_pages = list(context.pages)

    new_pages = []

    for candidate_page in after_pages:
        if candidate_page not in before_pages:
            new_pages.append(candidate_page)

    # 1. 새 창/새 탭으로 공유창이 열린 경우
    if new_pages:
        share_page = new_pages[-1]

        try:
            share_page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        share_page.wait_for_timeout(1000)

        share_url = (
            read_url_from_inputs(share_page)
            or read_url_from_visible_text(share_page)
        )

        try:
            share_page.close()
        except Exception:
            pass

        if share_url:
            print(f"공유 링크 추출 완료: {share_url}")
            return share_url

    # 2. 현재 상세페이지 안에 공유 모달이 뜬 경우
    share_url = (
        read_url_from_inputs(page)
        or read_url_from_visible_text(page)
    )

    if share_url:
        print(f"공유 링크 추출 완료: {share_url}")
        return share_url

    print("공유 링크를 찾지 못했습니다.")
    return ""


def reset_to_main_page(page):
    """
    다음 물품 검색을 위해 나라장터 메인 화면으로 돌아간다.

    상세페이지, 검색결과 화면, 팝업 상태가 꼬이는 것을 방지하기 위해
    물품 하나 처리 후 매번 메인 URL로 이동한다.
    """

    print("다음 검색을 위해 메인 화면으로 이동합니다.")

    try:
        page.goto(
            G2B_SHOP_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(1500)

        close_all_popups(page)

    except Exception as error:
        raise Exception(f"메인 화면 초기화 실패: {error}")
    
def extract_company_name_precise(page):
    """
    상세페이지에서 업체명/계약자명을 정확하게 추출한다.

    나라장터 상세페이지에서는 업체명이 보통 아래 형태로 들어간다.

    <span id="mf_wfm_container_ctentUntyGrpNm"
          class="w2textbox font20 txtGreen">주식회사 홍석</span>

    주변에 '계약자/공급자 정보조회' 버튼이 같이 있어서
    div 전체 텍스트로 추출하면 버튼 텍스트까지 섞일 수 있다.
    따라서 업체명 span만 직접 선택한다.
    """

    company_name_candidates = [
        page.locator("#mf_wfm_container_ctentUntyGrpNm"),
        page.locator("span#mf_wfm_container_ctentUntyGrpNm"),
        page.locator("span.w2textbox.font20.txtGreen"),
    ]

    for locator in company_name_candidates:
        try:
            count = locator.count()

            if count == 0:
                continue

            for index in range(count):
                target = locator.nth(index)

                if target.is_visible(timeout=1000):
                    company_name = clean_text(target.inner_text(timeout=3000))

                    if company_name:
                        return company_name

        except Exception:
            continue

    # 위 방식이 실패하면 기존 방식으로 보조 추출
    company_name = (
        extract_detail_value(page, "업체명")
        or extract_detail_value(page, "업체")
        or extract_detail_value(page, "계약업체")
        or extract_detail_value(page, "계약자")
        or extract_detail_value(page, "공급자")
        or extract_detail_value(page, "제조사")
    )

    # 혹시 fallback 결과에 버튼 텍스트가 섞이면 제거
    company_name = company_name.replace("계약자/공급자 정보조회", "")
    company_name = clean_text(company_name)

    return company_name

def find_product_result_rows(page, item_number):
    """
    검색 결과 화면에서 물품식별번호가 포함된 결과 행들을 모두 찾는다.

    목적:
    - 같은 물품식별번호로 검색했을 때 여러 상품/계약/가격이 나오면
      그 결과 행을 전부 수집하기 위함.
    """

    item_number = str(item_number).strip()

    print(f"검색 결과 행 전체 찾기: {item_number}")

    page.wait_for_timeout(1500)

    # 우선 tr 기준으로 찾는다.
    # tr이 가장 안정적이고, div는 너무 넓은 영역까지 잡을 수 있으므로 후순위로 둔다.
    row_locator_candidates = [
        ("tr", page.locator("tr").filter(has_text=item_number)),
        ("li", page.locator("li").filter(has_text=item_number)),
        ("div", page.locator("div").filter(has_text=item_number)),
    ]

    result_rows = []
    seen_texts = set()

    for label, locator in row_locator_candidates:
        try:
            count = locator.count()

            if count == 0:
                continue

            for index in range(count):
                row = locator.nth(index)

                try:
                    if not row.is_visible(timeout=1000):
                        continue
                except Exception:
                    continue

                try:
                    row_text = clean_text(row.inner_text(timeout=3000))
                except Exception:
                    continue

                if not row_text:
                    continue

                # 너무 큰 div 또는 중복 locator 방지
                if row_text in seen_texts:
                    continue

                seen_texts.add(row_text)
                result_rows.append(row)

            if result_rows:
                print(f"검색 결과 행 찾기 성공: {label}, {len(result_rows)}개")
                return result_rows

        except Exception:
            continue

    print(f"검색 결과 행을 찾지 못했습니다: {item_number}")
    return result_rows


def get_product_result_count(page, item_number):
    """
    검색 결과에서 해당 물품식별번호로 나온 결과 개수를 반환한다.
    """

    rows = find_product_result_rows(page, item_number)
    result_count = len(rows)

    print(f"{item_number} 검색 결과 개수: {result_count}개")

    return result_count


def find_product_click_target_by_index(page, item_number, result_index):
    """
    검색 결과 중 result_index 번째 상품의 클릭 대상을 찾는다.

    result_index는 0부터 시작한다.

    반환:
    - 클릭할 locator
    - 상세페이지 링크 후보
    - 전체 검색 결과 개수
    """

    rows = find_product_result_rows(page, item_number)

    if not rows:
        raise Exception(f"검색 결과에서 물품식별번호를 찾지 못했습니다: {item_number}")

    if result_index >= len(rows):
        raise Exception(
            f"검색 결과 순번이 범위를 벗어났습니다. "
            f"요청 순번: {result_index + 1}, 전체 결과: {len(rows)}"
        )

    row = rows[result_index]
    total_count = len(rows)

    print(f"검색 결과 {result_index + 1}/{total_count}번째 상품 선택")

    clickable_candidates = [
        (
            row.locator("a"),
            "결과 영역 내부 a"
        ),
        (
            row.locator("button"),
            "결과 영역 내부 button"
        ),
        (
            row.locator("[role='button']"),
            "결과 영역 내부 role button"
        ),
        (
            row.locator("[onclick]"),
            "결과 영역 내부 onclick"
        ),
    ]

    for clickable_locator, clickable_label in clickable_candidates:
        try:
            clickable_count = clickable_locator.count()

            if clickable_count == 0:
                continue

            for clickable_index in range(clickable_count):
                clickable = clickable_locator.nth(clickable_index)

                try:
                    if clickable.is_visible(timeout=1000):
                        print(f"클릭 대상 찾기 성공: {clickable_label}")

                        detail_link = extract_detail_link_from_locator(page, clickable)

                        if detail_link:
                            print(f"상세링크 후보 추출 성공: {detail_link}")
                        else:
                            print("클릭 대상에서 상세링크 후보를 찾지 못했습니다.")

                        return clickable, detail_link, total_count

                except Exception:
                    continue

        except Exception:
            continue

    # 내부 클릭 요소가 없으면 행 자체 클릭
    print("내부 클릭 요소가 없어 결과 행 자체를 클릭합니다.")

    detail_link = extract_detail_link_from_locator(page, row)

    if detail_link:
        print(f"상세링크 후보 추출 성공: {detail_link}")
    else:
        print("결과 행에서 상세링크 후보를 찾지 못했습니다.")

    return row, detail_link, total_count


def open_product_detail_from_search_result_by_index(page, item_number, result_index):
    """
    검색 결과 중 특정 순번의 상품을 클릭하여 상세페이지로 진입한다.

    반환:
    - detail_page
    - detail_link
    - total_count
    """

    target, detail_link, total_count = find_product_click_target_by_index(
        page,
        item_number,
        result_index
    )

    detail_page = click_target_and_get_detail_page(page, target)

    if not detail_link:
        detail_link = detail_page.url

    print(f"상세페이지 진입 완료: {detail_page.url}")
    print(f"저장할 상세페이지 링크 후보: {detail_link}")

    return detail_page, detail_link, total_count