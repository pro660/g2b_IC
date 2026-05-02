from datetime import datetime

from src.config import LOG_FILE_PATH


def write_log(message):
    """
    logs/app.log 파일에 로그를 기록한다.
    """

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE_PATH, "a", encoding="utf-8") as file:
        file.write(f"[{now}] {message}\n")