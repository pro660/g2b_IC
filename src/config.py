import sys
from pathlib import Path


def get_base_dir():
    """
    개발 중에는 프로젝트 폴더를 기준으로 하고,
    exe 실행 중에는 exe 파일이 있는 폴더를 기준으로 한다.
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

# 조달청 종합쇼핑몰 품목 등록 내역 CSV
G2B_FILE_DATA_PATH = DATA_DIR / "g2b_items.csv"


# ================================
# CSV / 브라우저 수집 설정
# ================================

# CSV 파일데이터를 우선 사용할지 여부
USE_FILE_DATA_FIRST = True

# 브라우저 보완 방식
#
# "off"
#   브라우저 자동화 사용 안 함.
#   CSV 결과만 저장한다.
#
# "csv_missing_only"
#   CSV에서 못 찾은 물품만 브라우저로 수집한다.
#   서버 부하를 가장 많이 줄이는 권장 설정.
#
# "all"
#   CSV에서 찾은 물품도 모두 브라우저로 보완한다.
#   구성, 옵션/기타, 상세페이지링크를 모두 채우고 싶을 때 사용.
BROWSER_COMPLEMENT_MODE = "all"


# ================================
# 서버 부하 방지 / 과도한 조회 방지 설정
# ================================

# 한 번 실행할 때 최대 처리할 물품 수
# None이면 제한 없음
MAX_ITEMS_PER_RUN = 500

# 한 번 실행할 때 브라우저로 실제 조회할 최대 물품 수
# None이면 제한 없음
MAX_BROWSER_ITEMS_PER_RUN = 100

# 물품 하나 처리가 끝난 뒤 다음 물품 처리 전 대기 시간
# 단위: 초
ITEM_DELAY_MIN_SECONDS = 3
ITEM_DELAY_MAX_SECONDS = 7

# 같은 물품식별번호 안에서 여러 상세페이지를 볼 때 대기 시간
# 단위: 초
DETAIL_DELAY_MIN_SECONDS = 1
DETAIL_DELAY_MAX_SECONDS = 3

# 일정 개수 처리 후 긴 휴식
# 예: 50개 처리 후 60초 휴식
PAUSE_EVERY_N_ITEMS = 50
PAUSE_SECONDS = 60

# 차단, 캡차, 과도한 요청, 접속 제한 의심 오류가 나오면 중단할지 여부
STOP_ON_BLOCK_LIKE_ERROR = True

# 차단 의심 오류 발생 시 대기 시간
# 단위: 초
RATE_LIMIT_BACKOFF_SECONDS = 300


def create_folders():
    """
    프로그램 실행에 필요한 폴더가 없으면 자동으로 생성한다.
    """

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)