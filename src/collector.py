from src.browser import open_browser, close_browser
from src.config import USE_FILE_DATA_FIRST, USE_BROWSER_DETAIL_COMPLEMENT
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
    print(message)

    if status_callback:
        status_callback(message)


def normalize_url(url):
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
        row["처리상태"] = "CSV수집완료"

        rows.append(row)

    return rows


def collect_product_info_hybrid(page, item_number, file_items, item_progress_callback=None):
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


def collect_product_info_browser_only(page, item_number, item_progress_callback=None):
    """
    CSV 결과가 없을 때 기존 브라우저 방식으로만 수집한다.
    """

    return collect_product_info_hybrid(
        page=page,
        item_number=item_number,
        file_items=[],
        item_progress_callback=item_progress_callback
    )


def collect_product_info(page, item_number, item_progress_callback=None):
    """
    물품식별번호 하나를 수집한다.

    우선순위:
    1. CSV 파일데이터에서 기본 계약정보 조회
    2. 설정에 따라 브라우저로 구성/옵션/공유링크 보완
    3. CSV 결과가 없으면 브라우저 방식으로 fallback
    """

    def update_item_progress(percent, message):
        if item_progress_callback:
            item_progress_callback(percent, message)

    file_items = []

    if USE_FILE_DATA_FIRST:
        update_item_progress(5, f"{item_number} CSV 데이터 조회 중")
        file_items = fetch_file_data_products(item_number)

    if file_items and not USE_BROWSER_DETAIL_COMPLEMENT:
        update_item_progress(90, f"{item_number} CSV 결과 정리 중")
        return collect_product_info_csv_only(item_number, file_items)

    if file_items and USE_BROWSER_DETAIL_COMPLEMENT:
        return collect_product_info_hybrid(
            page=page,
            item_number=item_number,
            file_items=file_items,
            item_progress_callback=item_progress_callback
        )

    update_item_progress(10, f"{item_number} CSV 결과 없음, 브라우저 수집으로 전환")

    return collect_product_info_browser_only(
        page=page,
        item_number=item_number,
        item_progress_callback=item_progress_callback
    )


def collect_all_products(
    item_numbers,
    status_callback=None,
    progress_callback=None,
    item_progress_callback=None,
    wait_for_enter=False
):
    """
    input.xlsx에서 읽은 물품식별번호 목록을 순회하면서 상품 정보를 수집한다.
    """

    results = []

    playwright = None
    browser = None
    context = None

    total_count = len(item_numbers)

    try:
        notify("브라우저 실행 중...", status_callback)

        if item_progress_callback:
            item_progress_callback(0, "브라우저 실행 준비 중")

        playwright, browser, context, page = open_browser()

        notify("나라장터 종합쇼핑몰 접속 완료", status_callback)

        if wait_for_enter:
            input("페이지가 정상적으로 열렸으면 Enter를 누르세요...")

        for index, item_number in enumerate(item_numbers, start=1):
            notify("=" * 60, status_callback)
            notify(f"[{index}/{total_count}] 물품식별번호 처리 시작: {item_number}", status_callback)

            try:
                if item_progress_callback:
                    item_progress_callback(0, f"{item_number} 처리 시작")

                reset_to_main_page(page)

                item_rows = collect_product_info(
                    page,
                    item_number,
                    item_progress_callback=item_progress_callback
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

            if item_progress_callback:
                item_progress_callback(97, f"{item_number} 엑셀 저장 중")

            save_to_excel(results)

            if item_progress_callback:
                item_progress_callback(100, f"{item_number} 저장 완료")

            notify(f"[{index}/{total_count}] 중간 저장 완료", status_callback)

        notify("=" * 60, status_callback)
        notify("전체 수집 완료", status_callback)

        if item_progress_callback:
            item_progress_callback(100, "전체 수집 완료")

    except Exception as error:
        notify(f"브라우저 실행 중 오류 발생: {error}", status_callback)

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
        if playwright is not None and browser is not None and context is not None:
            close_browser(playwright, browser, context)

    return results