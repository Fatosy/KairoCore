import re
from ..common.errors import (
    KCRE_USE_ERROR
)

class KcReTool:

    def validate_date_format(datestr: str, fmt: str = "%Y-%m-%d") -> bool:
        """
        验证日期字符串是否符合指定格式
        
        该函数使用正则表达式验证日期字符串是否符合预期的格式。
        
        Args:
            datestr (str): 待验证的日期字符串
            fmt (str, optional): 期望的日期格式。默认为 "%Y-%m-%d"
                支持的格式:
                - "%Y": 四位年份 (如: 2023)
                - "%Y-%m": 年月 (如: 2023-01)
                - "%Y-%m-%d": 年月日 (如: 2023-01-01)
                - "%Y-%m-%d %H:%M:%S": 完整日期时间 (如: 2023-01-01 12:00:00)
        
        Returns:
            bool: 如果日期字符串符合指定格式返回True，否则返回False
            
        Note:
            该函数仅验证格式，不验证日期的实际有效性（如2月30日）
        """
        time_re_dict  = {
            "%Y": r'^\d{4}$',
            "%m": r'^\d{2}$',
            "%d": r'^\d{2}$',
            "%H": r'^\d{2}$',
            "%M": r'^\d{2}$',
            "%S": r'^\d{2}$',
            "%Y-%m": r'^\d{4}-\d{2}$',
            "%Y-%m-%d": r'^\d{4}-\d{2}-\d{2}$',
            "%Y-%m-%d %H:%M:%S": r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$',
        }
        # 检查格式是否被支持
        if fmt not in time_re_dict:
            raise KCRE_USE_ERROR.msg_format(f'不支持的日期格式: {fmt}')
        
        try:
            # 使用对应格式的正则表达式进行匹配
            pattern = time_re_dict[fmt]
            return bool(re.match(pattern, datestr))
        except Exception as e:
            # 捕获正则表达式匹配过程中的异常
            return False