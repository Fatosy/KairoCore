import pytz
import datetime
from typing import Union, Literal, List

from ..common.errors import (
    KCT_TIME_PARAM_EMPTY_ERROR,
    KCT_TIME_CHANGE_ERROR,
    KCT_TIME_VALIDATE_ERROR
)


class Ktimer:

    def __init__(self):
        # 设置时区为北京时间
        self.tz = pytz.timezone('Asia/Shanghai')

    @staticmethod
    def get_timezone():
        """ 获取时区 - 默认北京时区 """
        return pytz.timezone('Asia/Shanghai')

    @staticmethod
    def format_datetime(change_datetime: Union[datetime.datetime, int, float, None], fmt: str="%Y-%m-%d %H:%M:%S") -> str:
        """
        获取带时区的当前日期和时间
        
        Args:
            change_datetime: datetime对象、时间戳（int/float）或None
            time_tmp: 日期格式化字符串
        
        Returns:
            str: 格式化后的日期时间字符串
        """
        if change_datetime is None:
            raise KCT_TIME_PARAM_EMPTY_ERROR
        
        if not isinstance(fmt, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间格式参数必须是字符串类型")
        
        bj_tz = Ktimer.get_timezone()
        
        # 如果输入是时间戳，则先转换为datetime对象
        if isinstance(change_datetime, (int, float)):
            # 将时间戳转换为UTC时间的datetime对象
            utc_datetime = datetime.datetime.fromtimestamp(change_datetime, pytz.utc)
            # 转换为北京时间
            change_datetime = utc_datetime.astimezone(bj_tz)
        
        return change_datetime.strftime(fmt)

    @staticmethod
    def get_current_datetime() -> datetime.datetime:
        """ 获取当前datetime时间 """
        bj_tz = Ktimer.get_timezone()
        return datetime.datetime.now(bj_tz)
    
    def add_time_delta(self, start_datetime: Union[datetime.datetime, int, float, None], days: int=0, seconds:int=0, 
            microseconds:int=0, milliseconds: int=0, minutes:int=0, hours:int=0, weeks:int=0) -> datetime.datetime:
        """
        向指定时间添加时间增量，支持时间戳和datetime对象输入
        
        Args:
            start_datetime: 起始时间，可以是datetime对象、时间戳（int/float）或None
            days: 天数增量
            seconds: 秒数增量
            microseconds: 微秒数增量
            milliseconds: 毫秒数增量
            minutes: 分钟数增量
            hours: 小时数增量
            weeks: 周数增量
        
        Returns:
            datetime.datetime: 调整后的时间（北京时间）
            
        Raises:
            KCT_TIME_PARAM_EMPTY_ERROR: 当start_datetime为None时抛出异常
        """
        if start_datetime is None:
            raise KCT_TIME_PARAM_EMPTY_ERROR
        
        bj_tz = Ktimer.get_timezone()

        change_datetime = start_datetime
        # 如果输入是时间戳，则先转换为datetime对象
        if isinstance(start_datetime, (int, float)):
            # 将时间戳转换为UTC时间的datetime对象
            utc_datetime = datetime.datetime.fromtimestamp(start_datetime, pytz.utc)
            # 转换为北京时间
            change_datetime = utc_datetime.astimezone(bj_tz)

        return change_datetime + datetime.timedelta(days=days, seconds=seconds, microseconds=microseconds,
                milliseconds=milliseconds, minutes=minutes, hours=hours, weeks=weeks)

    @staticmethod
    def get_timestamp(target_datetime: Union[datetime.datetime, None] = None) -> int:
        """
        将datetime对象转换为UTC时间戳，如果不提供参数则返回当前时间戳
        
        Args:
            target_datetime (datetime.datetime, optional): 要转换的datetime对象，
                如果为None则使用当前时间。默认为None。
        
        Returns:
            int: UTC时间戳（秒级）
        """
        bj_tz = Ktimer.get_timezone()

        # 如果没有提供时间，则使用当前时间
        if target_datetime is None:
            target_datetime = datetime.datetime.now(bj_tz)
        
        # 确保时间对象有时区信息
        if target_datetime.tzinfo is None:
            # 如果没有时区信息，假设为北京时间
            target_datetime = bj_tz.localize(target_datetime)
        
        # 转换为UTC时间并获取时间戳
        utc_datetime = target_datetime.astimezone(pytz.utc)
        return int(utc_datetime.timestamp())
    
    @staticmethod
    def parse_to_timestamp(time_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> int:
        """
        将时间字符串解析为UTC时间戳
        
        该函数将指定格式的时间字符串解析为datetime对象，并转换为UTC时间戳。
        输入的时间字符串被视为北京时间。
        
        Args:
            time_str (str): 时间字符串，如 "2023-01-01 12:00:00"
            fmt (str, optional): 时间字符串的格式。默认为 "%Y-%m-%d %H:%M:%S"
        
        Returns:
            int: UTC时间戳（秒级）
        """
        if not isinstance(time_str, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间参数必须是字符串类型")
        
        if not isinstance(fmt, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间格式参数必须是字符串类型")

        try:
            # 将字符串解析为 naive datetime 对象（不带时区）
            dt_naive = datetime.datetime.strptime(time_str, fmt)
            
            # 将naive datetime对象设置为北京时间
            bj_tz = Ktimer.get_timezone()
            dt_bj = bj_tz.localize(dt_naive)
            
            # 转换为 UTC 时间
            utc_datetime = dt_bj.astimezone(pytz.utc)
            
            # 转换为 Unix 时间戳（秒级）
            timestamp = int(utc_datetime.timestamp())
            
            return timestamp
        except ValueError as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"无法将 '{time_str}' 转成格式 '{fmt}': {str(e)}")

    @staticmethod
    def format_timestamp(timestamp: Union[int, float], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        将时间戳转换为指定格式的日期时间字符串（北京时间）
        
        该函数接收一个UTC时间戳，将其转换为北京时间，并按照指定格式进行格式化。
        
        Args:
            timestamp (Union[int, float]): UTC时间戳（秒级或毫秒级）
            fmt (str, optional): 日期时间格式字符串。默认为 "%Y-%m-%d %H:%M:%S"
        
        Returns:
            str: 格式化后的日期时间字符串（北京时间）
        """
        # 参数验证
        if timestamp is None:
            raise KCT_TIME_PARAM_EMPTY_ERROR
        
        if not isinstance(fmt, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间格式参数必须是字符串类型")

        bj_tz = Ktimer.get_timezone()
        try:
            # 处理毫秒级时间戳
            if timestamp > 1e10:  # 如果是毫秒时间戳
                timestamp = timestamp / 1000
            
            # 将时间戳转换为UTC时间
            utc_datetime = datetime.datetime.fromtimestamp(timestamp, pytz.utc)
            
            # 转换为北京时间
            local_datetime = utc_datetime.astimezone(bj_tz)
            
            # 格式化为字符串
            return local_datetime.strftime(fmt)
        except (ValueError, OSError) as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"无法转换时间戳 {timestamp}: {str(e)}")
        except Exception as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"时间戳转换过程中发生未知错误: {str(e)}")
    
    def time_diff(self, start_time: str, end_time: str, fmt: str = "%Y-%m-%d %H:%M:%S", 
              unit: Literal['second', 'minute', 'hour', 'day'] = 'second') -> float:
        """
        计算两个时间字符串之间的时间差
        
        该函数计算两个指定格式的时间字符串之间的时间差，并可以按不同单位返回结果。
        
        Args:
            start_time (str): 起始时间字符串
            end_time (str): 结束时间字符串
            fmt (str, optional): 时间字符串的格式。默认为 "%Y-%m-%d %H:%M:%S"
            unit (Literal['second', 'minute', 'hour', 'day'], optional): 返回结果的单位。
                可选值: 'second', 'minute', 'hour', 'day'。默认为 'second'
        
        Returns:
            float: 时间差值，单位由unit参数指定，保留2位小数
        """
        if not isinstance(start_time, str) or not isinstance(end_time, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间参数必须是字符串类型")
        
        if not isinstance(fmt, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间格式参数必须是字符串类型")

        valid_units = {'second', 'minute', 'hour', 'day'}
        if unit not in valid_units:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"单位参数必须是以下值之一: {valid_units}")
        
        try:
            # 将字符串转换为datetime对象
            datetime1 = datetime.datetime.strptime(start_time, fmt)
            datetime2 = datetime.datetime.strptime(end_time, fmt)
            # 计算时间差
            time_difference = datetime2 - datetime1
            # 获取时间差的总秒数（绝对值）
            total_seconds = abs(time_difference.total_seconds())
            # 根据指定单位转换结果
            unit_factors = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }
            result = total_seconds / unit_factors[unit]
            return round(result, 2)
        except ValueError as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"时间字符串格式错误: {str(e)}")
        except Exception as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"计算时间差时发生错误: {str(e)}")
    
    @staticmethod
    def is_time_after(earlier_time: str, later_time: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> bool:
        """
        比较两个时间字符串，判断后者是否在前者之后
        
        该函数比较两个指定格式的时间字符串，判断later_time是否在earlier_time之后。
        
        Args:
            earlier_time (str): 较早的时间字符串
            later_time (str): 较晚的时间字符串
            fmt (str, optional): 时间字符串的格式。默认为 "%Y-%m-%d %H:%M:%S"
        
        Returns:
            bool: 如果later_time在earlier_time之后返回True，否则返回False
            
        Raises:
            KCT_TIME_CHANGE_ERROR: 当时间字符串格式不正确或转换失败时抛出异常
        """
        # 参数验证
        if not isinstance(earlier_time, str) or not isinstance(later_time, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间参数必须是字符串类型")
        
        if not isinstance(fmt, str):
            raise KCT_TIME_CHANGE_ERROR.msg_format("时间格式参数必须是字符串类型")
        
        try:
            # 将字符串转换为datetime对象
            datetime1 = datetime.datetime.strptime(earlier_time, fmt)
            datetime2 = datetime.datetime.strptime(later_time, fmt)
            
            # 比较时间
            return datetime2 > datetime1
            
        except ValueError as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"时间字符串格式错误: {str(e)}")
        except Exception as e:
            raise KCT_TIME_CHANGE_ERROR.msg_format(f"比较时间时发生错误: {str(e)}")
        

    @staticmethod
    def validate_date_format(datestr: str, fmt: str = "%Y-%m-%d") -> bool:
        """
            验证是否为有效日期 
        """
        try:
            # 验证是否为有效日期
            date_obj = datetime.datetime.strptime(datestr, fmt).date()
            return datestr
        except ValueError:
            raise KCT_TIME_VALIDATE_ERROR.msg_format('无效的日期')