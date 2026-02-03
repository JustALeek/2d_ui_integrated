import picologging as logging
from datetime import datetime 

class LogColorFormatter(logging.Formatter):
    colors = {
        logging.DEBUG: "\x1b[38;20m",    # 회색
        logging.INFO: "\x1b[32;20m",     # 녹색
        logging.WARNING: "\x1b[33;20m",  # 노란색
        logging.ERROR: "\x1b[31;20m",    # 빨간색
        logging.CRITICAL: "\x1b[31;1m",  # 굵은 빨강
    }
    reset = "\x1b[0m"
    log_format = "%(custom_time)s - [%(levelname)s] - %(name)s - %(message)s"

    def format(self, record):
        record.message = record.getMessage()

        record.custom_time = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

        color = self.colors.get(record.levelno, self.reset)
        
        # 3. 매번 Formatter 객체를 만들지 말고, 문자열 포맷팅만 수행 (성능 최적화)
        formatted_msg = self.log_format % record.__dict__
        
        return f"{color}{formatted_msg}{self.reset}"