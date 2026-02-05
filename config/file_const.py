from pathlib import Path

SAVE_DIR = Path(__file__).resolve().parent.parent / "data_source"

JPG_EXTENSION = "jpg"
JSON_EXTENSION = "json"

JPG_LOAD_FAILED = "이미지 로드 실패: "
JSON_LOAD_FAILED = "JSON 로드 실패: "

JSON_READ_FAILED = "JSON 읽기 실패 "