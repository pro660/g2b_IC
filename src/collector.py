import random
import time

from src.browser import open_browser, close_browser
from src.config import (
    USE_FILE_DATA_FIRST,
    BROWSER_COMPLEMENT_MODE,
    MAX_ITEMS_PER_RUN,
    MAX_BROWSER_ITEMS_PER_RUN,
    ITEM_DELAY_MIN_SECONDS,
    ITEM_DELAY_MAX_SECONDS,
    DETAIL_DELAY_MIN_SECONDS,
    DETAIL_DELAY_MAX_SECONDS,
    PAUSE_EVERY_N_ITEMS,
    PAUSE_SECONDS,
    STOP_ON_BLOCK_LIKE_ERROR,
    RATE_LIMIT_BACKOFF_SECONDS
)
from src.excel_writer import save_to_excel
from src.filedata_client import (
    fetch_file_data_products,
    map_file_item_to_row
)
from src.g2b_page import (
    search_by_item_number,
    get_product_result_count,
    open_product_detail_from_search_result_by_index,
    extract_product_detail_info,
    extract_share_link_from_detail_page,
    reset_to_main_page
)


def notify(message, status_callback=None):
    """
    터미널과 GUI 양쪽에 상태 메시지를 전달하기 위한 함수.
    """

    print(message)

    if status_callback:
        status_callback(message)


def polite_delay(min_seconds, max_seconds, reason="", status_callback=None):
    """
    서버에 과도한 요청을 보내지 않기 위해 일정 시간 대기한다.

    min_seconds와 max_seconds 사이의 랜덤 시간만큼 쉰다.
    랜덤 딜레이를 사용하는 이유는 모든 요청이 기계적으로 같은 간격으로
    반복되는 것을 피하기 위함이다.
    """

    if min_seconds <= 0 and max_seconds <= 0:
        return

    delay_seconds = random.uniform(min_seconds, max_seconds)

    message = f"{reason} 대기 중... {delay_seconds:.1f}초"

    print(message)

    if status_callback:
        status_callback(message)

    time.sleep(delay_seconds)


def fixed_pause(seconds, reason="", status_callback=None):
    """
    일정 개수 처리 후 긴 휴식을 준다.
    """

    if seconds <= 0:
        return

    message = f"{reason} 장기 대기 중... {seconds}초"

    print(message)

    if status_callback:
        status_callback(message)

    time.sleep(seconds)


def is_block_like_error(error_message):
    """
    차단, 과도한 요청, 접속 제한, 캡차 등으로 의심되는 오류인지 확인한다.
    """

    if not error_message:
        return False

    message = str(error_message).lower()

    keywords = [
        "429",
        "too many",
        "rate limit",
        "captcha",
        "캡차",
        "차단",
        "접근 제한",
        "접속 제한",
        "일시적으로",
        "과도한",
        "비정상",
        "서비스 이용",
        "timeout",
        "timed out",
    ]

    for keyword in keywords:
        if keyword.lower() in message:
            return True

    return False


def should_use_browser(file_items):
    """
    브라우저 보완 수집 여부를 결정한다.

    BROWSER_COMPLEMENT_MODE 값에 따라 동작한다.

    "off":
        브라우저를 전혀 사용하지 않는다.

    "csv_missing_only":
        CSV에서 해당 물품을 찾지 못한 경우에만 브라우저를 사용한다.

    "all":
        모든 물품을 브라우저로 보완한다.
    """

    if BROWSER_COMPLEMENT_MODE == "off":
        return False

    if BROWSER_COMPLEMENT_MODE == "csv_missing_only":
        return not bool(file_items)

    if BROWSER_COMPLEMENT_MODE == "all":
        return True

    # 잘못된 설정값이면 안전하게 브라우저 사용을 최소화한다.
    return not bool(file_items)


def normalize_url(url):
    """
    URL 기준 중복 판단을 위해 문자열을 정리한다.
    """

    if url is None:
        return ""

    url = str(url).strip()
    url = url.replace("\n", "").replace("\r", "")

    if len(url) > 1 and url.endswith("/"):
        url = url.rstrip("/")

    return url


def make_empty_row(
    item_number,
    status,
    error_message="",
    result_order="",
    same_number_result_count=""
):
    """
    결과 엑셀에 저장할 기본 행 데이터를 만든다.
    """

    return {
        "물품식별번호": item_number,
        "검색결과순번": result_order,
        "동일번호결과수": same_number_result_count,
        "상품명": "",
        "업체명": "",
        "계약번호": "",
        "계약변경차수": "",
        "계약단가": "",
        "계약기간": "",
        "MAS여부": "",
        "계약유형": "",
        "공급지역": "",
        "인도조건": "",
        "쇼핑몰등록일자": "",
        "업체사업자등록번호": "",
        "대분류쇼핑카테고리": "",
        "중분류쇼핑카테고리": "",
        "물품분류번호": "",
        "세부품명번호": "",
        "상세페이지링크": "",
        "구성": "",
        "옵션/기타": "",
        "수집방식": "",
        "처리상태": status,
        "오류내용": error_message
    }


def merge_rows(base_row, detail_row):
    """
    CSV 기본정보와 브라우저 상세정보를 합친다.

    원칙:
    - 계약번호, 계약단가 등 CSV 기본정보는 유지한다.
    - 구성, 옵션/기타, 상세페이지링크는 브라우저 정보로 보완한다.
    - 상품명/업체명은 브라우저 값이 있으면 브라우저 값을 우선 사용한다.
    """

    merged = dict(base_row)

    for key, value in detail_row.items():
        value = "" if value is None else str(value).strip()

        if not value:
            continue

        # 브라우저 상세에서 더 정확히 가져오는 값
        if key in ["상품명", "업체명", "상세페이지링크", "구성", "옵션/기타"]:
            merged[key] = value

        # CSV에 비어 있는 값만 보완
        elif key not in merged or not str(merged.get(key, "")).strip():
            merged[key] = value

    return merged


def collect_browser_detail_by_index(
    page,
    item_number,
    result_index,
    result_count,
    item_progress_callback=None
):
    """
    검색 결과 중 특정 순번의 상품을 브라우저로 상세 수집한다.

    반환:
    - detail_row
    - dedupe_url
    """

    def update_item_progress(percent, message):
        if item_progress_callback:
            item_progress_callback(percent, message)

    result_order = result_index + 1

    update_item_progress(
        45,
        f"{item_number} {result_order}/{result_count}번째 상세페이지 진입 중"
    )

    detail_page, _, _ = open_product_detail_from_search_result_by_index(
        page,
        item_number,
        result_index
    )

    update_item_progress(
        65,
        f"{item_number} {result_order}/{result_count}번째 상품정보 추출 중"
    )

    detail_info = extract_product_detail_info(detail_page, item_number)

    update_item_progress(
        85,
        f"{item_number} {result_order}/{result_count}번째 공유 링크 추출 중"
    )

    share_link = extract_share_link_from_detail_page(detail_page)

    if share_link:
        detail_info["상세페이지링크"] = share_link
        dedupe_url = normalize_url(share_link)
    else:
        detail_info["상세페이지링크"] = detail_page.url
        dedupe_url = normalize_url(detail_page.url)

    detail_row = make_empty_row(
        item_number=item_number,
        status="브라우저상세수집완료",
        result_order=result_order,
        same_number_result_count=result_count
    )

    detail_row.update(detail_info)

    if not share_link:
        detail_row["처리상태"] = "브라우저상세수집완료_공유링크확인필요"

    if detail_page != page:
        try:
            detail_page.close()
        except Exception:
            pass

    return detail_row, dedupe_url


def collect_product_info_csv_only(item_number, file_items):
    """
    CSV 결과만 저장한다.
    브라우저 조회를 하지 않는다.
    """

    rows = []
    total_count = len(file_items)

    for index, file_item in enumerate(file_items, start=1):
        row = map_file_item_to_row(
            file_item=file_item,
            item_number=item_number,
            result_order=index,
            total_count=total_count
        )

        row["수집방식"] = "CSV"
        row["처리상태"] = "CSV수집완료_브라우저조회생략"

        rows.append(row)

    return rows


def collect_product_info_hybrid(
    page,
    item_number,
    file_items,
    item_progress_callback=None,
    status_callback=None
):
    """
    CSV로 기본정보를 먼저 가져오고,
    브라우저로 구성/옵션/공유링크를 보완한다.
    """

    def update_item_progress(percent, message):
        if item_progress_callback:
            item_progress_callback(percent, message)

    csv_rows = []

    for index, file_item in enumerate(file_items, start=1):
        csv_rows.append(
            map_file_item_to_row(
                file_item=file_item,
                item_number=item_number,
                result_order=index,
                total_count=len(file_items)
            )
        )

    collected_rows = []
    seen_detail_urls = set()

    update_item_progress(20, f"{item_number} 브라우저 검색 중")

    search_by_item_number(page, item_number)

    update_item_progress(35, f"{item_number} 검색 결과 확인 중")

    browser_result_count = get_product_result_count(page, item_number)

    if browser_result_count == 0:
        if csv_rows:
            for row in csv_rows:
                row["수집방식"] = "CSV"
                row["처리상태"] = "CSV수집완료_브라우저결과없음"
            return csv_rows

        raise Exception(f"검색 결과가 없습니다: {item_number}")

    total_result_count = max(browser_result_count, len(csv_rows))

    print(
        f"{item_number} 결과 개수: "
        f"CSV={len(csv_rows)}건, 브라우저={browser_result_count}건"
    )

    for result_index in range(browser_result_count):
        result_order = result_index + 1

        if result_index > 0:
            update_item_progress(
                10,
                f"{item_number} {result_order}/{browser_result_count}번째 결과 검색 준비 중"
            )

            reset_to_main_page(page)

            update_item_progress(
                20,
                f"{item_number} {result_order}/{browser_result_count}번째 결과 재검색 중"
            )

            search_by_item_number(page, item_number)

        detail_row, dedupe_url = collect_browser_detail_by_index(
            page=page,
            item_number=item_number,
            result_index=result_index,
            result_count=browser_result_count,
            item_progress_callback=item_progress_callback
        )

        if result_index < len(csv_rows):
            base_row = csv_rows[result_index]
        else:
            base_row = make_empty_row(
                item_number=item_number,
                status="브라우저상세수집완료",
                result_order=result_order,
                same_number_result_count=total_result_count
            )

        merged_row = merge_rows(base_row, detail_row)

        merged_row["검색결과순번"] = result_order
        merged_row["동일번호결과수"] = total_result_count
        merged_row["수집방식"] = "CSV+브라우저"
        merged_row["처리상태"] = "상품정보수집완료"

        if not merged_row.get("구성") and not merged_row.get("옵션/기타"):
            merged_row["처리상태"] = "상품정보수집완료_상세속성확인필요"

        if dedupe_url:
            if dedupe_url in seen_detail_urls:
                print(
                    f"중복 상세페이지 URL 감지로 저장 제외: "
                    f"{item_number} {result_order}/{browser_result_count}번째, {dedupe_url}"
                )
                continue

            seen_detail_urls.add(dedupe_url)

        collected_rows.append(merged_row)

        # 같은 물품식별번호 안에서 다음 상세페이지로 넘어가기 전 대기
        if result_index < browser_result_count - 1:
            polite_delay(
                DETAIL_DELAY_MIN_SECONDS,
                DETAIL_DELAY_MAX_SECONDS,
                reason=f"{item_number} 다음 상세페이지 이동 전 서버 부하 방지",
                status_callback=status_callback
            )

    # CSV에는 있는데 브라우저 결과 순번으로는 처리하지 못한 나머지 보존
    if len(csv_rows) > browser_result_count:
        for remain_index in range(browser_result_count, len(csv_rows)):
            row = csv_rows[remain_index]
            row["수집방식"] = "CSV"
            row["처리상태"] = "CSV수집완료_브라우저미보완"
            collected_rows.append(row)

    if not collected_rows:
        raise Exception(f"중복 제외 후 저장할 상품이 없습니다: {item_number}")

    update_item_progress(95, f"{item_number} 결과 정리 중")

    return collected_rows


def collect_product_info_browser_only(
    page,
    item_number,
    item_progress_callback=None,
    status_callback=None
):
    """
    CSV 결과가 없을 때 기존 브라우저 방식으로만 수집한다.
    """

    return collect_product_info_hybrid(
        page=page,
        item_number=item_number,
        file_items=[],
        item_progress_callback=item_progress_callback,
        status_callback=status_callback
    )


def collect_product_info_from_sources(
    page,
    item_number,
    file_items,
    use_browser,
    item_progress_callback=None,
    status_callback=None
):
    """
    이미 조회한 CSV 결과와 브라우저 사용 여부를 기준으로
    물품식별번호 하나를 수집한다.
    """

    def update_item_progress(percent, message):
        if item_progress_callback:
            item_progress_callback(percent, message)

    # 1. CSV 결과가 있고 브라우저를 쓰지 않는 경우
    if file_items and not use_browser:
        update_item_progress(90, f"{item_number} CSV 결과 정리 중")

        return collect_product_info_csv_only(
            item_number=item_number,
            file_items=file_items
        )

    # 2. CSV 결과가 있고 브라우저 보완을 하는 경우
    if file_items and use_browser:
        return collect_product_info_hybrid(
            page=page,
            item_number=item_number,
            file_items=file_items,
            item_progress_callback=item_progress_callback,
            status_callback=status_callback
        )

    # 3. CSV 결과가 없고 브라우저를 쓰는 경우
    if not file_items and use_browser:
        update_item_progress(10, f"{item_number} CSV 결과 없음, 브라우저 수집으로 전환")

        return collect_product_info_browser_only(
            page=page,
            item_number=item_number,
            item_progress_callback=item_progress_callback,
            status_callback=status_callback
        )

    # 4. CSV 결과도 없고 브라우저도 꺼져 있는 경우
    return [
        make_empty_row(
            item_number=item_number,
            status="CSV결과없음_브라우저조회비활성화",
            error_message="CSV에서 해당 물품식별번호를 찾지 못했고 브라우저 조회가 비활성화되어 있습니다."
        )
    ]


def open_browser_if_needed(browser_state, status_callback=None, item_progress_callback=None):
    """
    브라우저가 필요한 순간에만 실행한다.

    CSV만으로 처리되는 물품이 많을 경우,
    브라우저를 아예 열지 않아서 웹 요청을 크게 줄일 수 있다.
    """

    if browser_state["page"] is not None:
        return

    notify("브라우저 실행 중...", status_callback)

    if item_progress_callback:
        item_progress_callback(0, "브라우저 실행 준비 중")

    playwright, browser, context, page = open_browser()

    browser_state["playwright"] = playwright
    browser_state["browser"] = browser
    browser_state["context"] = context
    browser_state["page"] = page

    notify("나라장터 종합쇼핑몰 접속 완료", status_callback)


def close_browser_if_opened(browser_state):
    """
    열린 브라우저가 있으면 종료한다.
    """

    playwright = browser_state.get("playwright")
    browser = browser_state.get("browser")
    context = browser_state.get("context")

    if playwright is not None and browser is not None and context is not None:
        close_browser(playwright, browser, context)


def collect_all_products(
    item_numbers,
    status_callback=None,
    progress_callback=None,
    item_progress_callback=None,
    wait_for_enter=False
):
    """
    input.xlsx에서 읽은 물품식별번호 목록을 순회하면서 상품 정보를 수집한다.

    서버 부하 방지 정책:
    - CSV 파일데이터를 우선 사용한다.
    - CSV에서 찾은 항목은 기본적으로 브라우저 조회를 생략한다.
    - CSV에 없는 항목만 브라우저로 조회한다.
    - 브라우저는 필요한 순간에만 실행한다.
    - 물품 하나 처리 후 랜덤 대기한다.
    - 일정 개수 처리 후 장기 대기한다.
    - 차단/과도한 요청 의심 오류가 발생하면 중단한다.
    """

    results = []

    total_count = len(item_numbers)

    browser_stats = {
        "browser_item_count": 0
    }

    browser_state = {
        "playwright": None,
        "browser": None,
        "context": None,
        "page": None
    }

    if MAX_ITEMS_PER_RUN is not None and total_count > MAX_ITEMS_PER_RUN:
        notify(
            f"입력 물품 수가 {total_count}개입니다. "
            f"이번 실행에서는 최대 {MAX_ITEMS_PER_RUN}개만 처리합니다.",
            status_callback
        )

        item_numbers = item_numbers[:MAX_ITEMS_PER_RUN]
        total_count = len(item_numbers)

    try:
        for index, item_number in enumerate(item_numbers, start=1):
            notify("=" * 60, status_callback)
            notify(f"[{index}/{total_count}] 물품식별번호 처리 시작: {item_number}", status_callback)

            used_browser_for_this_item = False

            try:
                if item_progress_callback:
                    item_progress_callback(0, f"{item_number} 처리 시작")

                file_items = []

                if USE_FILE_DATA_FIRST:
                    if item_progress_callback:
                        item_progress_callback(5, f"{item_number} CSV 데이터 조회 중")

                    file_items = fetch_file_data_products(item_number)

                use_browser = should_use_browser(file_items)

                if use_browser:
                    if MAX_BROWSER_ITEMS_PER_RUN is not None:
                        if browser_stats["browser_item_count"] >= MAX_BROWSER_ITEMS_PER_RUN:
                            notify(
                                f"브라우저 조회 제한 도달: "
                                f"{browser_stats['browser_item_count']}개 / {MAX_BROWSER_ITEMS_PER_RUN}개",
                                status_callback
                            )

                            if file_items:
                                item_rows = collect_product_info_csv_only(
                                    item_number=item_number,
                                    file_items=file_items
                                )

                                for row in item_rows:
                                    row["처리상태"] = "CSV수집완료_브라우저제한으로미보완"

                            else:
                                item_rows = [
                                    make_empty_row(
                                        item_number=item_number,
                                        status="브라우저수집제한으로미수집",
                                        error_message="MAX_BROWSER_ITEMS_PER_RUN 제한에 도달했습니다."
                                    )
                                ]

                            results.extend(item_rows)

                            if item_progress_callback:
                                item_progress_callback(100, f"{item_number} 브라우저 제한으로 종료")

                            save_to_excel(results)
                            notify(f"[{index}/{total_count}] 중간 저장 완료", status_callback)
                            continue

                    open_browser_if_needed(
                        browser_state=browser_state,
                        status_callback=status_callback,
                        item_progress_callback=item_progress_callback
                    )

                    if wait_for_enter:
                        input("페이지가 정상적으로 열렸으면 Enter를 누르세요...")

                    reset_to_main_page(browser_state["page"])

                    browser_stats["browser_item_count"] += 1
                    used_browser_for_this_item = True

                item_rows = collect_product_info_from_sources(
                    page=browser_state["page"],
                    item_number=item_number,
                    file_items=file_items,
                    use_browser=use_browser,
                    item_progress_callback=item_progress_callback,
                    status_callback=status_callback
                )

                results.extend(item_rows)

                notify(
                    f"[{index}/{total_count}] 수집 성공: {item_number}, "
                    f"{len(item_rows)}개 상품 저장",
                    status_callback
                )

            except Exception as error:
                error_message = str(error)

                notify(f"[{index}/{total_count}] 수집 실패: {item_number}", status_callback)
                notify(f"오류 내용: {error_message}", status_callback)

                row = make_empty_row(
                    item_number=item_number,
                    status="실패",
                    error_message=error_message
                )

                results.append(row)

                if item_progress_callback:
                    item_progress_callback(100, f"{item_number} 실패")

                # 차단/과도한 요청 의심 오류면 긴 대기 후 중단
                if is_block_like_error(error_message):
                    fixed_pause(
                        RATE_LIMIT_BACKOFF_SECONDS,
                        reason="차단 또는 과도한 요청 의심 오류 감지",
                        status_callback=status_callback
                    )

                    if STOP_ON_BLOCK_LIKE_ERROR:
                        notify(
                            "차단/과도한 요청 의심 오류로 인해 수집을 중단합니다.",
                            status_callback
                        )
                        break

            if item_progress_callback:
                item_progress_callback(97, f"{item_number} 엑셀 저장 중")

            save_to_excel(results)

            if item_progress_callback:
                item_progress_callback(100, f"{item_number} 저장 완료")

            notify(f"[{index}/{total_count}] 중간 저장 완료", status_callback)

            # 일정 개수마다 긴 휴식
            # CSV만 처리한 경우에는 웹 요청이 없으므로 긴 휴식 필요성이 낮지만,
            # 브라우저 조회가 포함된 실행에서는 안전하게 적용한다.
            if index < total_count and PAUSE_EVERY_N_ITEMS:
                if used_browser_for_this_item and index % PAUSE_EVERY_N_ITEMS == 0:
                    fixed_pause(
                        PAUSE_SECONDS,
                        reason=f"{index}개 처리 완료, 서버 부하 방지",
                        status_callback=status_callback
                    )

            # 브라우저를 실제 사용한 경우에만 다음 웹 요청 전 대기
            if index < total_count and used_browser_for_this_item:
                polite_delay(
                    ITEM_DELAY_MIN_SECONDS,
                    ITEM_DELAY_MAX_SECONDS,
                    reason="다음 브라우저 조회 전 서버 부하 방지",
                    status_callback=status_callback
                )

        notify("=" * 60, status_callback)
        notify("전체 수집 완료", status_callback)
        notify(
            f"브라우저로 실제 조회한 물품 수: {browser_stats.get('browser_item_count', 0)}개",
            status_callback
        )

        if item_progress_callback:
            item_progress_callback(100, "전체 수집 완료")

    except Exception as error:
        notify(f"수집 실행 중 오류 발생: {error}", status_callback)

        if not results:
            for item_number in item_numbers:
                results.append(
                    make_empty_row(
                        item_number=item_number,
                        status="실패",
                        error_message=str(error)
                    )
                )

            save_to_excel(results)

        if item_progress_callback:
            item_progress_callback(100, "오류 발생")

    finally:
        close_browser_if_opened(browser_state)

    return results