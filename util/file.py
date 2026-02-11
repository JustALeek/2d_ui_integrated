import os
import cv2

from config import file_const

class File():

    def __init__(self):
        self.path = file_const.SAVE_JPG_DIR
        self.path2 = file_const.SAVE_VIS_DIR
        self.path.mkdir(parents = True, exist_ok = True)
        self.path2.mkdir(parents = True, exist_ok = True)

    # .jpg 파일 저장
    def save_jpg(self, frame, timestamp, visualization = False):
        save_path = self.path2 if visualization else self.path
        jpg_path = save_path / f"IMG_{timestamp}_vis.{file_const.JPG_EXTENSION}" if visualization else save_path / f"IMG_{timestamp}.{file_const.JPG_EXTENSION}"
        cv2.imwrite(str(jpg_path), frame)

    # .jpg 파일 전체 불러오기 / 시작 화면
    def get_all_jpg(self):
        jpg_files = list(self.path.glob(f"*.{file_const.JPG_EXTENSION}"))

        jpg_files.sort(reverse=True)

        return jpg_files, file_const.SAVE_JPG_DIR

    # .jpg 파일 열기 / 보기 기능
    def get_jpg(self, filename):
        img_path = self.path / f"{filename}"

        return img_path

    # 폴더 열기
    def get_path(self):

        return self.path

    # 가장 마지막에 찍힌 파일 가져오기
    def get_last_img(self):
        jpg_files = list(self.path.glob(f"*.{file_const.JPG_EXTENSION}"))

        last_jpg_file = max(jpg_files, key = os.path.getmtime)

        return last_jpg_file, file_const.SAVE_JPG_DIR
