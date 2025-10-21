from ..utils.panic import Panic
from .http import HttpStatusCode

# mysql session 异常 业务代码 10010 ~ 10021
MQSN_INIT_ERROR = Panic(10010, "Mysql配置异常，请检查env配置！")
MQSN_PARAM_KEY_PATCH_ERROR = Panic(10011, "Mysql语句未匹配到对应参数，请检查！")
MQSNT_PARAM_NONE_ERROR = Panic(10012, "生成语句的参数不能为空，请检查！")


# kc_timer 异常 业务代码 10030 ~ 10039
KCT_TIME_PARAM_EMPTY_ERROR = Panic(10030, "时间参数不能为空，请检查！")
KCT_TIME_CHANGE_ERROR = Panic(10031, "时间转换失败，请检查")
KCT_TIME_VALIDATE_ERROR = Panic(10032, "时间验证错误，请检查！")


# kc_zookeeper 异常 业务代码 10040 ~ 10049
KCZ_CONNECT_ERROR = Panic(10040, "zookeeper连接异常，请检查！")
KCZ_USE_ERROR = Panic(10041, "zookeeper使用异常，请检查！")


# kc_redis 异常 业务代码 10050 ~ 10059
KCR_CONNECT_ERROR = Panic(10050, "redis连接异常，请检查！")
KCR_USE_ERROR = Panic(10051, "redis使用异常，请检查！")


# kc_re 异常 业务代码 10060 ~ 10069
KCRE_USE_ERROR = Panic(10060, "正则校验异常，请检查！")


# kc_http 异常 业务代码 10070 ~ 10079
KCHT_INIT_ERROR = Panic(10070, "http配置异常，请检查！")
KCHT_REQUEST_ERROR = Panic(10071, "http请求异常，请检查！")
KCHT_TIMEOUT_ERROR = Panic(10072, "http请求超时，请检查！")
KCHT_STATUS_ERROR = Panic(10073, "http状态码异常，请检查！")
KCHT_PARSE_ERROR = Panic(10074, "http响应解析异常，请检查！")

# kc_upload 异常 业务代码 10080 ~ 10089
KCU_SAVE_DIR_EMPTY_ERROR = Panic(10080, "保存目录为空", HttpStatusCode.BAD_REQUEST)
KCU_MKDIR_ERROR = Panic(10081, "创建目录失败", HttpStatusCode.INTERNAL_SERVER_ERROR)
KCU_FILENAME_EMPTY_ERROR = Panic(10082, "文件名为空", HttpStatusCode.BAD_REQUEST)
KCU_PARAM_MISSING_ERROR = Panic(10083, "缺少必要参数", HttpStatusCode.BAD_REQUEST)
KCU_BASE64_PARSE_ERROR = Panic(10084, "Base64 内容解析失败", HttpStatusCode.UNPROCESSABLE_ENTITY)
KCU_UPLOAD_SAVE_ERROR = Panic(10085, "文件上传失败", HttpStatusCode.INTERNAL_SERVER_ERROR)
KCU_BASE64_SAVE_ERROR = Panic(10086, "Base64 上传失败", HttpStatusCode.INTERNAL_SERVER_ERROR)

# kc_file_upload_route 异常 业务代码 10090 ~ 10099
KCFU_UPLOAD_FAIL_ERROR = Panic(10090, "文件上传失败", HttpStatusCode.INTERNAL_SERVER_ERROR)
KCFU_BASE64_UPLOAD_FAIL_ERROR = Panic(10091, "Base64 上传失败", HttpStatusCode.INTERNAL_SERVER_ERROR)

# kc_panic 辅助方法异常 业务代码 10100 ~ 10109
KCP_EXEC_AWAITABLE_TYPE_ERROR = Panic(10100, "exec_with_route_error: awaitable 参数必须是可等待对象", HttpStatusCode.BAD_REQUEST)
KCP_EXEC_PANIC_CONST_TYPE_ERROR = Panic(10101, "exec_with_route_error: error_const 参数必须是 Panic 实例", HttpStatusCode.BAD_REQUEST)