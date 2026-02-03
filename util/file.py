import os
import cv2
import json
import numpy as np
import picologging as logging

from datetime import datetime
from config import file_const

class File():

    def __init__(self):
        self.path = file_const.SAVE_DIR
        self.path.mkdir(parents = True, exist_ok = True)
            
    # .jpg / .json 파일 저장
    def save_jpg_json(self, frame, json_data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

        jpg_path = self.path / f"IMG_{timestamp}.{file_const.JPG_EXTENTION}"
        cv2.imwrite(str(jpg_path), frame)

        json_path = self.path / f"IMG_{timestamp}.{file_const.JSON_EXTENTION}"

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4)

    # .jpg 파일 저장
    def save_jpg(self, frame, timestamp):
        jpg_path = self.path / f"IMG_{timestamp}.{file_const.JPG_EXTENTION}"
        cv2.imwrite(str(jpg_path), frame)


    # .jpg 파일 전체 불러오기 / 시작 화면
    def get_all_jpg(self):
        jpg_files = list(self.path.glob(f"*.{file_const.JPG_EXTENTION}"))

        jpg_files.sort(reverse=True)

        return jpg_files, file_const.SAVE_DIR

    # .jpg / .json 파일 불러오기 / 파일명, 검사시간 클릭 시
    def get_jpg_json_by_filename(self, filename):
        frame = None
        json_data = None
        
        img_path = self.path / f"{filename}.{file_const.JPG_EXTENTION}"
        json_path = self.path / f"{filename}.{file_const.JSON_EXTENTION}"

        try:
            img_array = np.fromfile(str(img_path), np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"{file_const.JPG_LOAD_FAILED}{e}")
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            print(f"{file_const.JSON_LOAD_FAILED}{e}")
        
        return frame, json_data

    # .jpg 파일 열기 / 보기 기능
    def get_jpg(self, filename):
        img_path = self.path / f"{filename}"

        return img_path


    # .jpg / .json 파일 삭제 / 삭제 기능
    def delete_jpg_json(self, filename):
        img_path = self.path / f"{filename}.{file_const.JPG_EXTENTION}"
        json_path = self.path / f"{filename}.{file_const.JSON_EXTENTION}"

        return img_path, json_path


    # 폴더 열기
    def get_path(self):

        return self.path
    
    # 로그 내보내기
    def get_all_jpg_json(self):
        jpg_files = sorted(self.path.glob(f"*.{file_const.JPG_EXTENTION}"))
        json_files = []

        for jpg_path in jpg_files:
            json_path = jpg_path.with_suffix(f".{file_const.JSON_EXTENTION}")
            json_content = {}

            try:
                with open(json_path, 'r', encoding = 'utf-8') as f:
                    json_content = json.load(f)
            except Exception as e:
                print(f"{file_const.JSON_READ_FAILED}({json_path.name}): {e}")

            json_files.append(json_content)

        return jpg_files, json_files

    # 가장 마지막에 찍힌 파일 가져오기
    def get_last_img(self):
        jpg_files = list(self.path.glob(f"*.{file_const.JPG_EXTENTION}"))

        last_jpg_file = max(jpg_files, key = os.path.getmtime)

        return last_jpg_file, file_const.SAVE_DIR
