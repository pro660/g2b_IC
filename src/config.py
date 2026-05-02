import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def get_base_dir():
    """
    개발 중에는 프로젝트 폴더를 기준으로 하고,
    exe 실행 중에는 exe 파일이 있는 폴더를 기준으로 한다.
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()

load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

INPUT_EXCEL_PATH = DATA_DIR / "input.xlsx"
OUTPUT_EXCEL_PATH = OUTPUT_DIR / "result.xlsx"
FAILED_EXCEL_PATH = OUTPUT_DIR / "failed_result.xlsx"
LOG_FILE_PATH = LOG_DIR / "app.log"

ITEM_NUMBER_COLUMN = "물품식별번호"

G2B_SHOP_URL = "https://shop.g2b.go.kr/"

# CSV 파일데이터
G2B_FILE_DATA_PATH = DATA_DIR / "g2b_items.csv"

USE_FILE_DATA_FIRST = True
USE_BROWSER_DETAIL_COMPLEMENT = True

# 기존 API 설정은 남겨둬도 됨
DATA_GO_KR_SERVICE_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()

G2B_API_URL = (
    "http://apis.data.go.kr/1230000/at/"
    "ShoppingMallPrdctInfoService/getMASCntrctPrdctInfoList"
)

API_NUM_OF_ROWS = 100
API_TYPE = "json"
API_INQRY_DIV = "1"
API_REQUEST_DELAY_SECONDS = 0.2


def create_folders():
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)