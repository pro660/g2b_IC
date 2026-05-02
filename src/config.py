import sys
from pathlib import Path


def get_base_dir():
    """
    프로젝트 기준 경로를 반환한다.

    개발 중:
        g2b_collector/

    exe 실행 중:
        exe 파일이 있는 폴더
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


# 프로젝트 최상위 폴더
BASE_DIR = get_base_dir()

# 폴더 경로
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

# 파일 경로
INPUT_EXCEL_PATH = DATA_DIR / "input.xlsx"
OUTPUT_EXCEL_PATH = OUTPUT_DIR / "result.xlsx"
FAILED_EXCEL_PATH = OUTPUT_DIR / "failed_result.xlsx"
LOG_FILE_PATH = LOG_DIR / "app.log"

# 입력 엑셀 컬럼명
ITEM_NUMBER_COLUMN = "물품식별번호"

# 나라장터 종합쇼핑몰 주소
G2B_SHOP_URL = "https://shop.g2b.go.kr/"


def create_folders():
    """
    프로그램 실행에 필요한 폴더가 없으면 자동으로 생성한다.
    """

    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)