import pandas as pd

from src.config import INPUT_EXCEL_PATH, ITEM_NUMBER_COLUMN


def normalize_item_number(value):
    """
    엑셀에서 읽은 물품식별번호를 문자열로 정리한다.

    엑셀에서 숫자로 저장된 경우 12345678.0처럼 읽힐 수 있기 때문에
    불필요한 .0을 제거한다.
    """
    if pd.isna(value):
        return ""

    item_number = str(value).strip()

    if item_number.endswith(".0"):
        item_number = item_number[:-2]

    return item_number


def read_item_numbers():
    """
    data/input.xlsx 파일에서 물품식별번호 목록을 읽는다.
    """

    if not INPUT_EXCEL_PATH.exists():
        raise FileNotFoundError(
            f"입력 엑셀 파일이 없습니다: {INPUT_EXCEL_PATH}"
        )

    df = pd.read_excel(INPUT_EXCEL_PATH)

    if ITEM_NUMBER_COLUMN not in df.columns:
        raise ValueError(
            f"input.xlsx에 '{ITEM_NUMBER_COLUMN}' 컬럼이 없습니다."
        )

    item_numbers = []

    for value in df[ITEM_NUMBER_COLUMN]:
        item_number = normalize_item_number(value)

        if item_number:
            item_numbers.append(item_number)

    # 중복 제거
    item_numbers = list(dict.fromkeys(item_numbers))

    if not item_numbers:
        raise ValueError("input.xlsx에서 읽을 물품식별번호가 없습니다.")

    return item_numbers