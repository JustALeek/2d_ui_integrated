# initUI
WINDOW_TITLE = "Smart Footwear Inspection System - Master Consle"
WINDOW_RESIZE = (1600, 950)

##################################################################
# initLeftStreamingUI
REALTIME_STREAMING_TITLE_TEXT = "🎥 실시간 스트리밍 모니터"

VIDEO_STREAMING_TEXT = "카메라 대기 중..."

RESOLUTION_CONFIG_TEXT = "영상 해상도 설정"
RESOLUTION_ITEAMS = [
    "Low (480x270)", 
    "Medium (640x480)", 
    "High (1280x720)",
    "4K_High (3840x2160)"
    ]
RESOLUTION_DEFAULT_INDEX = 1

CAPTURE_BUTTON_TEXT = "📸 캡처 및 검사 ( Space/Enter )"
CAPTURE_BUTTON_MINIMUM_HEIGHT = 70

##################################################################
# initRightImageUI
ANALYSIS_RESULT_TITLE_TEXT = "📊 검사 분석 결과 (실시간 시각화)"
RESULT_IMAGE_TEXT = "이력 목록에서 항목을 선택하십시오"

##################################################################
# initRightThresholdUI
THRESHOLD_TITLE_TEXT = "⚙️ Threshold 민감도 설정"
THRESHOLD_TEXT = "임계값: "
THRESHOLD_DEFAULT_VALUE = "10%"

##################################################################
# initRightHistoryUI
HISTORY_TITLE_TEXT = "📜 검사 이력 관리 및 업로드"
ALL_SELECT_CHECKBOX_TEXT = "전체 선택"
EXPORT_LOG_TEXT = "📑 로그 내보내기"
CHECKED_UPLOAD_TEXT = "☁️ 일괄 업로드"
OPEN_FOLDER_TEXT = "📁 폴더 열기"

HISTORY_TABLE_HEADER_SELECT_TEXT = "선택"
HISTORY_TABLE_HEADER_FILENAME_TEXT = "파일명"
HISTORY_TABLE_HEADER_TEST_TIME_TEXT = "검사시간"
HISTORY_TABLE_HEADER_STATUS_TEXT = "상태"
HISTORY_TABLE_HEADER_ACTION_TEXT = "액션"

HISTORY_TABLE_DEFAULT_STATUS_VALUE_TEXT = " 대기 "

##################################################################
# on_resolution_changed
RESOLUTION_LOW = (480, 270)
RESOLUTION_MEDIUM = (640, 480)
RESOLUTION_HIGH = (1280, 720)
RESOLUTION_4K_HIGH = (3840, 2160)

##################################################################
# export_log_file
LOG_EXPORT_FALILED_TITLE_TEXT = "내보내기 실패"
LOG_EXPORT_FALILED_CONTENT_TEXT = "기록된 데이터가 없습니다."

LOG_EXPORT_TEXT = "로그 내보내기"
LOG_EXPORT_FILENAME = "Inspection_Log_"
LOG_EXPORT_EXTENTION = "jsonl"

LOG_EXPORT_ERROR_TEXT = "로그 내보내기 중 오류 발생: "

##################################################################
# open_folder
EXCEPTION_TITLE_TEXT = "오류"
EXCEPTION_CONTENT_TEXT = "폴더를 열 수 없습니다: "

##################################################################
# create_action_buttons
LOOK_TEXT = "보기"
DELETE_TEXT = "삭제"
UPLOAD_TEXT = "업로드"

##################################################################
# delete_file
DELETE_REPLY_TITLE_TEXT = "삭제 확인"
DELETE_REPLY_CONTENT_TEXT = "와 관련된 모든 데이터를 삭제하시겠습니까?"

DELETE_FAILED_TITLE_TEXT = "오류"
DELETE_FAILED_CONTENT_TEXT = "파일 삭제 실패: "

##################################################################
# upload_file
CHANGE_STATUS_TEXT = "✅ 완료"

BUTTON_TEXT = "업로드"

SUCCESS_TITLE_TEXT = "업로드 완료"
SUCCESS_CONTENT_TEXT = "성공적으로 업로드되었습니다:"

##################################################################
#upload_all

BATCH_UPLOAD_SUCCESS_TITLE_TEXT = "일괄 업로드 완료"
BATCH_UPLOAD_SUCCESS_CONTENT_TEXT= "건의 항목이 업로드되었습니다."

NO_CHECK_EXCEPTION_TITLE_TEXT = "선택 없음"
NO_CHECK_EXCEPTION_CONTENT_TEXT = "업로드할 항목을 체크해주세요."