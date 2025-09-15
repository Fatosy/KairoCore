from ..utils.panic import Panic

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