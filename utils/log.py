""" 日志配置和管理。"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

# 加载 .env 环境变量（支持向上查找）
load_dotenv(find_dotenv())

# --- 配置常量 ---
# 日志文件名
LOG_FILENAME = "karo_api.log"
# 默认日志级别（可通过 .env 中的 LOG_LEVEL 覆盖）
def _parse_log_level(level_str: str | None) -> int:
    """将字符串或数字形式的日志级别解析为 logging 的整型级别。"""
    if not level_str:
        return logging.DEBUG
    s = str(level_str).strip()
    # 若为数字，直接解析
    if s.isdigit():
        try:
            return int(s)
        except Exception:
            return logging.DEBUG
    # 映射常用级别名称
    mapping = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET,
    }
    return mapping.get(s.upper(), logging.DEBUG)

DEFAULT_LOG_LEVEL = _parse_log_level(os.getenv("LOG_LEVEL", "DEBUG"))
# 日志目录名
LOG_DIR_NAME = "logs"
# 日志轮转间隔 (天)
LOG_ROTATION_DAYS = 1
# 保留日志文件的天数
KEEP_LOG_DAYS = 30

# --- 自定义日志格式器 ---
class ApiLogFormatter(logging.Formatter):
    """自定义日志格式化器，用于文件输出。"""
    def format(self, record):
        # 获取当前时间
        dt = datetime.fromtimestamp(record.created)
        # 格式化时间
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        # 获取日志级别
        level_tag = record.levelname
        # 获取文件名
        filename = os.path.basename(record.pathname)
        # 构建自定义消息格式: [级别][年月日时分秒][文件名:行号]: 消息
        # 使用 : 分隔文件名和行号更符合常规日志格式
        log_message = f"[{level_tag}][{time_str}][{filename}:{record.lineno}]: {record.getMessage()}"
        # 如果有异常信息，也添加进去
        if record.exc_info:
            log_message += f"\n{self.formatException(record.exc_info)}"
        return log_message

# --- 带颜色的日志格式器 ---
class ColoredLogFormatter(logging.Formatter):
    """
    带颜色的日志格式化器，用于控制台输出。
    """
    
    # ANSI颜色代码
    COLORS = {
        'ERROR': '\033[91m',    # 红色
        'WARNING': '\033[93m',  # 黄色
        'INFO': '\033[94m',     # 脚本蓝色
        'DEBUG': '\033[96m',    # 青色
        'CRITICAL': '\033[95m', # 紫色
        'RESET': '\033[0m'      # 重置颜色
    }
    
    def format(self, record):
        # 获取当前时间
        dt = datetime.fromtimestamp(record.created)
        # 格式化时间
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        # 获取日志级别
        level_tag = record.levelname
        # 获取文件名
        filename = os.path.basename(record.pathname)
        
        # 构建日志消息内容
        message_content = record.getMessage()
        
        # 根据日志级别添加颜色
        color_start = self.COLORS.get(level_tag, '')
        color_end = self.COLORS['RESET'] if color_start else ''
        
        # 构建带颜色的消息
        # 使用 : 分隔文件名和行号更符合常规日志格式
        colored_message = f"{color_start}[{level_tag}][{time_str}][{filename}:{record.lineno}]: {message_content}{color_end}"
        
        # 添加异常信息（如果存在）
        if record.exc_info:
            colored_message += f"\n{self.formatException(record.exc_info)}"
        
        return colored_message

# --- 配置日志记录器 ---
def configure_logger(log_level: int = DEFAULT_LOG_LEVEL, logs_dir: str = "."):
    """
    配置 Karo CoreLog 的全局日志记录器。

    Args:
        log_level (int): 日志级别。默认为 DEBUG
        logs_dir (str): 存放日志文件的根目录。默认为当前目录 ('.')。
    """
    # 设置日志目录
    log_directory = os.path.join(logs_dir, LOG_DIR_NAME)
    # 确保日志目录存在
    os.makedirs(log_directory, exist_ok=True)
    log_file_path = os.path.join(log_directory, LOG_FILENAME)

    # 获取或创建 'Karo Core' 记录器
    logger = logging.getLogger("Karo Core")
    # 设置记录器级别
    logger.setLevel(log_level)
    # 禁止向 root 传播，避免被其他全局处理器影响
    logger.propagate = False

    # 避免重复添加处理器
    if not logger.handlers:
        # 1. 文件处理器 (带轮转)
        # when='D' 表示按天轮转, interval=1 表示每天轮转
        # backupCount 根据保留天数计算，确保至少保留指定天数的日志
        backup_count = max(1, KEEP_LOG_DAYS // LOG_ROTATION_DAYS)
        file_handler = TimedRotatingFileHandler(
            log_file_path, when="D", interval=LOG_ROTATION_DAYS, 
            backupCount=backup_count, encoding='utf-8',
        )
        file_handler.setLevel(log_level)
        # 文件日志使用无颜色格式器
        file_formatter = ApiLogFormatter()
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # 2. 控制台处理器 (用于开发)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        # 控制台日志使用彩色格式器
        console_formatter = ColoredLogFormatter() 
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        logger.info(f"Karo Core 日志已配置，日志文件: {log_file_path}, "
                    f"轮转周期: {LOG_ROTATION_DAYS}天, 保留天数: {KEEP_LOG_DAYS}天")
    else:
        # 已存在处理器时，按新级别更新所有处理器级别
        for h in logger.handlers:
            try:
                h.setLevel(log_level)
            except Exception:
                pass

    return logger

# --- 获取已配置的记录器实例 ---
def get_logger():
    """获取 'Karo Core' 记录器实例。"""
    # 每次获取 logger 时，根据当前环境变量解析日志级别，避免默认参数在定义时被固定
    env_level = _parse_log_level(os.getenv("LOG_LEVEL", "DEBUG"))
    return configure_logger(log_level=env_level)

# --- 运行时调整日志级别 ---
def set_log_level(level: int | str):
    """
    在运行时动态调整日志级别。

    Args:
        level: 日志级别的名称或数字（例如 'INFO' 或 20）。
    """
    logger = logging.getLogger("Karo Core")
    new_level = _parse_log_level(str(level))
    logger.setLevel(new_level)
    for h in logger.handlers:
        try:
            h.setLevel(new_level)
        except Exception:
            pass
    return logger