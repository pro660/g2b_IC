import io
import pandas as pd

from src.config import G2B_FILE_DATA_PATH


_cached_df = None


def clean_text(value):
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    value = str(value).strip()

    # 컬럼명이나 값에 붙은 큰따옴표 제거
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1].strip()

    return value


def decode_file_content(file_path):
    """
    조달청 파일데이터를 텍스트로 디코딩한다.

    이 파일은 일반 CSV처럼 보이지만,
    실제로는 UTF-16 계열이거나 탭 구분 파일일 수 있다.
    """

    raw = file_path.read_bytes()

    if not raw:
        print(f"CSV 파일이 비어 있습니다: {file_path}")
        return ""

    encodings = [
        "utf-8-sig",
        "cp949",
        "euc-kr",
        "utf-8",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
    ]

    last_error = None

    for encoding in encodings:
        try:
            text = raw.decode(encoding)

            # 정상 파일이면 이 단어들이 들어있어야 함
            if "물품식별번호" in text or "계약번호" in text:
                print(f"CSV 텍스트 디코딩 성공: encoding={encoding}")
                return text

            # 디코딩은 됐지만 원하는 보고서 내용이 아닌 경우
            print(f"디코딩은 됐지만 주요 컬럼을 찾지 못함: encoding={encoding}")

        except Exception as error:
            last_error = error
            continue

    print(f"CSV 디코딩 실패. 마지막 오류: {last_error}")
    return ""


def find_header_line_index(lines):
    """
    파일 앞부분의 검색조건/출력일자 설명을 건너뛰고,
    실제 컬럼명이 시작되는 줄을 찾는다.
    """

    for index, line in enumerate(lines):
        normalized = line.replace('"', "").strip()

        if "물품식별번호" in normalized and "계약번호" in normalized:
            return index

    return -1


def read_csv_from_report_text(text):
    """
    조달청 보고서 텍스트에서 실제 데이터 영역만 잘라 DataFrame으로 변환한다.
    """

    if not text:
        return pd.DataFrame()

    lines = text.splitlines()

    header_index = find_header_line_index(lines)

    if header_index < 0:
        print("CSV에서 실제 헤더 줄을 찾지 못했습니다.")
        print("파일 안에 '물품식별번호', '계약번호' 컬럼이 있는지 확인하세요.")
        return pd.DataFrame()

    print(f"CSV 실제 헤더 줄 발견: {header_index + 1}번째 줄")

    data_text = "\n".join(lines[header_index:])

    separators = [
        "\t",
        ",",
        "|",
        ";",
    ]

    last_error = None

    for separator in separators:
        try:
            print(f"CSV 파싱 시도: sep={repr(separator)}")

            df = pd.read_csv(
                io.StringIO(data_text),
                dtype=str,
                sep=separator,
                engine="python",
                quotechar='"'
            )

            if df.empty:
                print(f"CSV 파싱은 됐지만 데이터가 비어 있습니다: sep={repr(separator)}")
                continue

            if len(df.columns) <= 1:
                print(f"컬럼이 1개뿐이라 구분자 재시도: sep={repr(separator)}")
                continue

            # 컬럼명 정리
            df.columns = [clean_text(column) for column in df.columns]

            print(f"CSV 파싱 성공: sep={repr(separator)}, {len(df)}행, {len(df.columns)}컬럼")
            return df

        except Exception as error:
            last_error = error
            continue

    print(f"CSV 파싱 실패. 마지막 오류: {last_error}")
    return pd.DataFrame()


def load_g2b_file_data():
    """
    data/g2b_items.csv 파일을 읽어 캐시한다.
    """

    global _cached_df

    if _cached_df is not None:
        return _cached_df

    if not G2B_FILE_DATA_PATH.exists():
        print(f"CSV 파일이 없습니다: {G2B_FILE_DATA_PATH}")
        _cached_df = pd.DataFrame()
        return _cached_df

    text = decode_file_content(G2B_FILE_DATA_PATH)
    df = read_csv_from_report_text(text)

    if df.empty:
        print("CSV 데이터가 비어 있어 브라우저 수집으로 전환합니다.")
        _cached_df = pd.DataFrame()
        return _cached_df

    _cached_df = df

    print("CSV 컬럼 목록:")
    for column in df.columns:
        print(f"- {column}")

    return _cached_df


def find_column(df, candidates):
    """
    후보 컬럼명 중 실제 CSV에 존재하는 첫 컬럼명을 반환한다.
    """

    columns = list(df.columns)

    for candidate in candidates:
        if candidate in columns:
            return candidate

    # 완전일치 실패 시 포함 검색
    for candidate in candidates:
        for column in columns:
            if candidate in column:
                return column

    return ""


def get_first_value(row, candidates):
    """
    row에서 후보 컬럼명 기준으로 첫 번째 값을 가져온다.
    """

    for column in candidates:
        if column in row.index:
            value = clean_text(row.get(column))

            if value:
                return value

    return ""


def normalize_item_number(value):
    """
    물품식별번호를 문자열로 정리한다.
    """

    value = clean_text(value)

    if value.endswith(".0"):
        value = value[:-2]

    return value


def fetch_file_data_products(item_number):
    """
    CSV 파일데이터에서 물품식별번호 기준으로 행을 찾는다.
    """

    item_number = normalize_item_number(item_number)

    if not item_number:
        return []

    try:
        df = load_g2b_file_data()
    except Exception as error:
        print(f"CSV 데이터 로드 실패. 브라우저 수집으로 전환합니다: {error}")
        return []

    if df.empty:
        print("CSV 데이터가 비어 있어 브라우저 수집으로 전환합니다.")
        return []

    item_number_column = find_column(
        df,
        [
            "물품식별번호",
            "물품식별번호값",
            "물품식별",
            "품목식별번호",
            "물품번호",
        ]
    )

    if not item_number_column:
        print("CSV에서 물품식별번호 컬럼을 찾지 못했습니다. 브라우저 수집으로 전환합니다.")
        print("현재 CSV 컬럼 목록:")
        for column in df.columns:
            print(f"- {column}")
        return []

    temp = df.copy()
    temp[item_number_column] = temp[item_number_column].apply(normalize_item_number)

    matched_df = temp[temp[item_number_column] == item_number]

    print(f"CSV 매칭 결과: {item_number}, {len(matched_df)}건")

    return matched_df.to_dict("records")


def map_file_item_to_row(file_item, item_number, result_order="", total_count=""):
    """
    CSV 1행을 result.xlsx 저장용 row로 변환한다.
    """

    row_series = pd.Series(file_item)

    product_name = get_first_value(
        row_series,
        [
            "품목",
            "물품식별명",
            "세부품명",
            "품명",
            "물품분류명",
            "상품명",
        ]
    )

    company_name = get_first_value(
        row_series,
        [
            "업체",
            "업체명",
            "계약업체",
            "공급업체",
        ]
    )

    contract_no = get_first_value(
        row_series,
        [
            "계약번호",
            "계약번호값",
        ]
    )

    contract_change_order = get_first_value(
        row_series,
        [
            "변경차수",
            "계약변경차수",
        ]
    )

    contract_price = get_first_value(
        row_series,
        [
            "단가",
            "계약단가",
            "계약단위값",
        ]
    )

    contract_period = get_first_value(
        row_series,
        [
            "계약기간",
            "계약시작일자",
            "계약종료일자",
        ]
    )

    mas_yn = get_first_value(
        row_series,
        [
            "MAS여부",
        ]
    )

    contract_type = get_first_value(
        row_series,
        [
            "계약구분",
            "계약유형",
        ]
    )

    supply_area = get_first_value(
        row_series,
        [
            "공급지역",
        ]
    )

    delivery_condition = get_first_value(
        row_series,
        [
            "인도조건",
        ]
    )

    mall_reg_date = get_first_value(
        row_series,
        [
            "쇼핑몰등록일자",
        ]
    )

    business_no = get_first_value(
        row_series,
        [
            "업체사업자등록번호",
            "사업자등록번호",
        ]
    )

    category_large = get_first_value(
        row_series,
        [
            "대분류쇼핑카테고리",
        ]
    )

    category_middle = get_first_value(
        row_series,
        [
            "중분류쇼핑카테고리",
        ]
    )

    item_class_no = get_first_value(
        row_series,
        [
            "물품분류번호",
        ]
    )

    detail_item_no = get_first_value(
        row_series,
        [
            "세부품명번호",
        ]
    )

    return {
        "물품식별번호": str(item_number).strip(),
        "검색결과순번": result_order,
        "동일번호결과수": total_count,
        "상품명": product_name,
        "업체명": company_name,
        "계약번호": contract_no,
        "계약변경차수": contract_change_order,
        "계약단가": contract_price,
        "계약기간": contract_period,
        "MAS여부": mas_yn,
        "계약유형": contract_type,
        "공급지역": supply_area,
        "인도조건": delivery_condition,
        "쇼핑몰등록일자": mall_reg_date,
        "업체사업자등록번호": business_no,
        "대분류쇼핑카테고리": category_large,
        "중분류쇼핑카테고리": category_middle,
        "물품분류번호": item_class_no,
        "세부품명번호": detail_item_no,
        "상세페이지링크": "",
        "구성": "",
        "옵션/기타": "",
        "수집방식": "CSV",
        "처리상태": "CSV수집완료",
        "오류내용": "",
    }