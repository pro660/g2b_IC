from src.browser import open_browser, close_browser
from src.excel_writer import save_to_excel
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
        "상세페이지링크": "",
        "구성": "",
        "옵션/기타": "",
        "처리상태": status,
        "오류내용": error_message
    }


def collect_one_search_result(
    page,
    item_number,
    result_index,
    result_count,
    item_progress_callback=None
):
    """
    같은 물품식별번호 검색 결과 중 특정 순번 하나를 수집한다.

    반환:
    - row
    - dedupe_url

    dedupe_url은 공유 버튼에서 추출한 실제 상세페이지 링크를 기준으로 한다.
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

    row = make_empty_row(
        item_number=item_number,
        status="상품정보수집완료",
        result_order=result_order,
        same_number_result_count=result_count
    )

    row.update(detail_info)

    if not share_link:
        row["처리상태"] = "상품정보수집완료_공유링크확인필요"

    if not row["구성"] and not row["옵션/기타"]:
        row["처리상태"] = "상세페이지진입완료_추출확인필요"

    if detail_page != page:
        try:
            detail_page.close()
        except Exception:
            pass

    return row, dedupe_url


def collect_product_info(page, item_number, item_progress_callback=None):
    """
    물품식별번호 하나를 검색하고, 검색 결과에 나온 모든 상품을 수집한다.

    핵심:
    - 같은 물품식별번호에서 여러 검색 결과가 나오면 전부 확인한다.
    - 단, 공유 버튼에서 추출한 상세페이지 URL이 이미 수집된 URL이면 중복으로 보고 저장하지 않는다.

    반환값:
    [
        row1,
        row2,
        ...
    ]
    """

    def update_item_progress(percent, message):
        if item_progress_callback:
            item_progress_callback(percent, message)

    collected_rows = []
    seen_detail_urls = set()

    update_item_progress(20, f"{item_number} 검색 중")

    search_by_item_number(page, item_number)

    update_item_progress(35, f"{item_number} 검색 결과 확인 중")

    result_count = get_product_result_count(page, item_number)

    if result_count == 0:
        raise Exception(f"검색 결과가 없습니다: {item_number}")

    print(f"{item_number} 검색 결과 개수: {result_count}개")

    for result_index in range(result_count):
        result_order = result_index + 1

        # 첫 번째 결과는 이미 검색된 화면을 사용한다.
        # 두 번째 결과부터는 상세페이지에서 돌아오는 상태 꼬임을 막기 위해 다시 검색한다.
        if result_index > 0:
            update_item_progress(
                10,
                f"{item_number} {result_order}/{result_count}번째 결과 검색 준비 중"
            )

            reset_to_main_page(page)

            update_item_progress(
                20,
                f"{item_number} {result_order}/{result_count}번째 결과 재검색 중"
            )

            search_by_item_number(page, item_number)

        row, dedupe_url = collect_one_search_result(
            page=page,
            item_number=item_number,
            result_index=result_index,
            result_count=result_count,
            item_progress_callback=item_progress_callback
        )

        # URL 기준 중복 제거
        if dedupe_url:
            if dedupe_url in seen_detail_urls:
                print(
                    f"중복 상세페이지 URL 감지로 저장 제외: "
                    f"{item_number} {result_order}/{result_count}번째, {dedupe_url}"
                )
                continue

            seen_detail_urls.add(dedupe_url)

        collected_rows.append(row)

    update_item_progress(95, f"{item_number} 결과 정리 중")

    if not collected_rows:
        raise Exception(f"중복 제외 후 저장할 상품이 없습니다: {item_number}")

    return collected_rows


def collect_all_products(
    item_numbers,
    status_callback=None,
    progress_callback=None,
    item_progress_callback=None,
    wait_for_enter=False
):
    """
    input.xlsx에서 읽은 물품식별번호 목록을 순회하면서 상품 정보를 수집한다.

    변경점:
    - 물품식별번호 1개에서 검색 결과가 여러 개 나오면 전부 확인한다.
    - 상세페이지 공유 URL이 같은 상품은 중복으로 판단하여 저장하지 않는다.
    - 가격/계약이 달라 URL이 다르면 같은 물품식별번호라도 별도 행으로 저장한다.
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