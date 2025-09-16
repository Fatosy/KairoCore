from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from KairoCore import KcReTool, Ktimer
from enum import IntEnum, Enum

from common.errors import (
    SCM_USER_PARAM_VALIDATE_ERROR
)


# 用户性别
class UserSex(str, Enum):
    MAN = "man"
    WOMAN = "woman"


# 用户会员
class UserVip(IntEnum):
    YES = 1
    NO = 0



# 用户新增
class UserAddor(BaseModel):
    name: str = Field(description="用户名")
    phone: str = Field(description="手机号")
    location: Optional[str] = Field(default=None, description="地址， 非必填")
    birthday: Optional[str] = Field(default=None, description="生日， 非必填")
    sex: Optional[UserSex] = Field(default=UserSex.MAN, description="性别, 默认男，非必填")
    is_vip: Optional[UserVip] = Field(default=UserVip.NO, description="是否是会员，默认非会员，非必填")

    @field_validator('birthday')
    def validate_date_format(cls, v):
        if v is not None:
            if not KcReTool.validate_date_format(v):
                raise SCM_USER_PARAM_VALIDATE_ERROR.msg_format("时间参数格式错误，请检查！")
            Ktimer.validate_date_format(v)
        return v

class UserAddtorList(BaseModel):
    items: List[UserAddor] = Field(description="用户列表")


# 用户修改
class UserUpdator(UserAddor):
    id: int = Field(description="用户id")

class UserUpdatorList(BaseModel):
    items: List[UserUpdator] = Field(description="用户列表")


# 用户删除
class UserDeletor(BaseModel):
    ids: List[int] = Field(description="用户id")


class UserQuery(BaseModel):
    limit: Optional[int] = Field(default=20, description="查询数量")
    offset: Optional[int] = Field(default=1, description="页码")


# 用户查询
class UserQueryBody(BaseModel):
    name: Optional[str] = Field(default=None, description="用户名")
    phone: Optional[str] = Field(default=None, description="手机号")
    sex: Optional[UserSex] = Field(default=None, description="性别")
    location: Optional[str] = Field(default=None, description="地址")
    birthday_start: Optional[str] = Field(default=None, description="生日起始")
    birthday_end: Optional[str] = Field(default=None, description="生日结束")

    @field_validator('birthday_start', 'birthday_end')
    def validate_date_format(cls, v):
        if v is not None:
            if not KcReTool.validate_date_format(v):
                raise SCM_USER_PARAM_VALIDATE_ERROR.msg_format("时间参数格式错误，请检查！")
            Ktimer.validate_date_format(v)
        return v
    

# 用户options
class UserInfoOptionsGettor(BaseModel):
    name: Optional[str] = Field(None, description="用户名称")