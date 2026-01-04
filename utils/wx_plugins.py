import xml.etree.ElementTree as ET
import time
import base64
import string
import random
import hashlib
import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import socket
from types import SimpleNamespace


class WxReceiveMsg(object):
    """
    微信接收消息基类
    """
    def __init__(self, xmlData):
        self.ToUserName = xmlData.find('ToUserName').text
        self.FromUserName = xmlData.find('FromUserName').text
        self.CreateTime = xmlData.find('CreateTime').text
        self.MsgType = xmlData.find('MsgType').text
        self.MsgId = xmlData.find('MsgId').text
        self.Encrypt = xmlData.find('Encrypt').text


class WxReceiveTextMsg(WxReceiveMsg):
    """
    微信接收文本消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.Content = xmlData.find('Content').text.encode("utf-8")


class WxReceiveImageMsg(WxReceiveMsg):
    """
    微信接收图片消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.PicUrl = xmlData.find('PicUrl').text
        self.MediaId = xmlData.find('MediaId').text

class WxReceiveVoiceMsg(WxReceiveMsg):
    """
    微信接收语音消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.MediaId = xmlData.find('MediaId').text
        self.Format = xmlData.find('Format').text
        self.MediaId16K = xmlData.find('MediaId16K').text

class WxReceiveVideoMsg(WxReceiveMsg):
    """
    微信接收视频消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.MediaId = xmlData.find('MediaId').text
        self.ThumbMediaId = xmlData.find('ThumbMediaId').text


class WxReceiveShortVideoMsg(WxReceiveMsg):
    """
    微信接收短视频消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.MediaId = xmlData.find('MediaId').text
        self.ThumbMediaId = xmlData.find('ThumbMediaId').text

class WxReceiveLocationMsg(WxReceiveMsg):
    """
    微信接收位置消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.Location_X = xmlData.find('Location_X').text
        self.Location_Y = xmlData.find('Location_Y').text
        self.Scale = xmlData.find('Scale').text
        self.Label = xmlData.find('Label').text


class WxReceiveLinkMsg(WxReceiveMsg):
    """
    微信接收链接消息类
    """
    def __init__(self, xmlData):
        WxReceiveMsg.__init__(self, xmlData)
        self.Title = xmlData.find('Title').text
        self.Description = xmlData.find('Description').text
        self.Url = xmlData.find('Url').text


class WxReplyMsg(object):
    """
    微信回复消息基类
    """
    def __init__(self):
        pass

    def send(self):
        return "success"


class WxReplyTextMsg(WxReplyMsg):
    """
    微信回复文本消息类
    """
    def __init__(self, toUserName, fromUserName, content):
        self.__dict = dict()
        self.__dict['ToUserName'] = toUserName
        self.__dict['FromUserName'] = fromUserName
        self.__dict['CreateTime'] = int(time.time())
        self.__dict['Content'] = content

    def send(self):
        XmlForm = """
            <xml>
                <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                <CreateTime>{CreateTime}</CreateTime>
                <MsgType><![CDATA[text]]></MsgType>
                <Content><![CDATA[{Content}]]></Content>
            </xml>
            """
        return XmlForm.format(**self.__dict)


class WxReplyImageMsg(WxReplyMsg):  
    """
    微信回复图片消息类
    """
    def __init__(self, toUserName, fromUserName, mediaId):
        self.__dict = dict()
        self.__dict['ToUserName'] = toUserName
        self.__dict['FromUserName'] = fromUserName
        self.__dict['CreateTime'] = int(time.time())
        self.__dict['MediaId'] = mediaId

    def send(self):
        XmlForm = """
            <xml>
                <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                <CreateTime>{CreateTime}</CreateTime>
                <MsgType><![CDATA[image]]></MsgType>
                <Image>
                <MediaId><![CDATA[{MediaId}]]></MediaId>
                </Image>
            </xml>
            """
        return XmlForm.format(**self.__dict)

class WxReplyVoiceMsg(WxReplyMsg):
    """
    微信回复语音消息类
    """
    def __init__(self, toUserName, fromUserName, mediaId):
        self.__dict = dict()
        self.__dict['ToUserName'] = toUserName
        self.__dict['FromUserName'] = fromUserName
        self.__dict['CreateTime'] = int(time.time())
        self.__dict['MediaId'] = mediaId

    def send(self):
        XmlForm = """
            <xml>
                <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                <CreateTime>{CreateTime}</CreateTime>
                <MsgType><![CDATA[voice]]></MsgType>
                <Voice>
                <MediaId><![CDATA[{MediaId}]]></MediaId>
                </Voice>
            </xml>
            """
        return XmlForm.format(**self.__dict)

class WxReplyVideoMsg(WxReplyMsg):
    """
    微信回复视频消息类
    """
    def __init__(self, toUserName, fromUserName, mediaId, title, description):
        self.__dict = dict()
        self.__dict['ToUserName'] = toUserName
        self.__dict['FromUserName'] = fromUserName
        self.__dict['CreateTime'] = int(time.time())
        self.__dict['MediaId'] = mediaId
        self.__dict['Title'] = title
        self.__dict['Description'] = description
    
    def send(self):
        XmlForm = """
            <xml>
                <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                <CreateTime>{CreateTime}</CreateTime>
                <MsgType><![CDATA[video]]></MsgType>
                <Video>
                    <MediaId><![CDATA[{MediaId}]]></MediaId>
                    <Title><![CDATA[{Title}]]></Title>
                    <Description><![CDATA[{Description}]]></Description>
                </Video>
            </xml>
            """
        return XmlForm.format(**self.__dict)

class WxReplyMusicMsg(WxReplyMsg):
    """
    微信回复音乐消息类
    """
    def __init__(self, toUserName, fromUserName, mediaId, title, description, musicUrl, hqMusicUrl, thumbMediaId):
        self.__dict = dict()
        self.__dict['ToUserName'] = toUserName
        self.__dict['FromUserName'] = fromUserName
        self.__dict['CreateTime'] = int(time.time())
        self.__dict['MediaId'] = mediaId
        self.__dict['Title'] = title
        self.__dict['Description'] = description
        self.__dict['MusicUrl'] = musicUrl
        self.__dict['HQMusicUrl'] = hqMusicUrl
        self.__dict['ThumbMediaId'] = thumbMediaId
    
    def send(self):
        XmlForm = """
            <xml>
                <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                <CreateTime>{CreateTime}</CreateTime>
                <MsgType><![CDATA[music]]></MsgType>
                <Music>
                    <MediaId><![CDATA[{MediaId}]]></MediaId>
                    <Title><![CDATA[{Title}]]></Title>
                    <Description><![CDATA[{Description}]]></Description>
                    <MusicUrl><![CDATA[{MusicUrl}]]></MusicUrl>
                    <HQMusicUrl><![CDATA[{HQMusicUrl}]]></HQMusicUrl>
                    <ThumbMediaId><![CDATA[{ThumbMediaId}]]></ThumbMediaId>
                </Music>
            </xml>
            """
        return XmlForm.format(**self.__dict)

class WxReplyNewsMsg(WxReplyMsg):
    """
    微信回复图文类消息类
    """
    def __init__(self, toUserName, fromUserName, title, description, picurl, Url):
        self.__dict = dict()
        self.__dict['ToUserName'] = toUserName
        self.__dict['FromUserName'] = fromUserName
        self.__dict['CreateTime'] = int(time.time())
        self.__dict['Title'] = title
        self.__dict['Description'] = description
        self.__dict['PicUrl'] = picurl
        self.__dict['Url'] = Url

    def send(self):
        XmlForm = """
            <xml>
                <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                <CreateTime>{CreateTime}</CreateTime>
                <MsgType><![CDATA[news]]></MsgType>
                <ArticleCount>1</ArticleCount>
                <Articles>
                    <item>
                    <Title><![CDATA[{Title}]]></Title>
                    <Description><![CDATA[{Description}]]></Description>
                    <PicUrl><![CDATA[{PicUrl}]]></PicUrl>
                    <Url><![CDATA[{Url}]]></Url>
                    </item>
                </Articles>
            </xml>
            """
        return XmlForm.format(**self.__dict)

def wx_parse_receive_xml(web_data):
    """
    解析微信接收消息XML
    """
    if len(web_data) == 0:
        return None
    xmlData = ET.fromstring(web_data)
    msg_type = xmlData.find('MsgType').text
    if msg_type == 'text':
        return WxReceiveTextMsg(xmlData)
    elif msg_type == 'image':
        return WxReceiveImageMsg(xmlData)
    elif msg_type == 'voice':
        return WxReceiveVoiceMsg(xmlData)
    elif msg_type == 'video':
        return WxReceiveVideoMsg(xmlData)
    elif msg_type == 'shortvideo':
        return WxReceiveShortVideoMsg(xmlData)
    elif msg_type == 'location':
        return WxReceiveLocationMsg(xmlData)
    elif msg_type == 'link':
        return WxReceiveLinkMsg(xmlData)



###############################   加解密   ##########################################
# Description:定义错误码含义 
WXBizMsgCrypt_OK = 0
WXBizMsgCrypt_ValidateSignature_Error = -40001
WXBizMsgCrypt_ParseXml_Error = -40002
WXBizMsgCrypt_ComputeSignature_Error = -40003
WXBizMsgCrypt_IllegalAesKey = -40004
WXBizMsgCrypt_ValidateAppid_Error = -40005
WXBizMsgCrypt_EncryptAES_Error = -40006
WXBizMsgCrypt_DecryptAES_Error = -40007
WXBizMsgCrypt_IllegalBuffer = -40008
WXBizMsgCrypt_EncodeBase64_Error = -40009
WXBizMsgCrypt_DecodeBase64_Error = -40010
WXBizMsgCrypt_GenReturnXml_Error = -40011


"""
关于Crypto.Cipher模块，ImportError: No module named 'Crypto'解决方案
请到官方网站 https://www.dlitz.net/software/pycrypto/ 下载pycrypto。
下载后，按照README中的“Installation”小节的提示进行pycrypto安装。
"""
class FormatException(Exception):
    pass

def throw_exception(message, exception_class=FormatException):
    """my define raise exception function"""
    raise exception_class(message)

class SHA1:
    """计算公众平台的消息签名接口"""

    def getSHA1(self, token, timestamp, nonce, encrypt):
        """用SHA1算法生成安全签名
        @param token:  票据
        @param timestamp: 时间戳
        @param encrypt: 密文
        @param nonce: 随机字符串
        @return: 安全签名
        """
        try:
            sortlist = [token, timestamp, nonce, encrypt]
            # 统一转为字符串进行排序与拼接，再编码为bytes供hashlib使用
            sortlist = [s if isinstance(s, str) else s.decode("utf-8") for s in sortlist]
            sortlist.sort()
            sha = hashlib.sha1()
            sha.update("".join(sortlist).encode("utf-8"))
            return  WXBizMsgCrypt_OK, sha.hexdigest()
        except Exception as e:
            #print e
            return  WXBizMsgCrypt_ComputeSignature_Error, None


class XMLParse:
    """提供提取消息格式中的密文及生成回复消息格式的接口"""

    # xml消息模板
    AES_TEXT_RESPONSE_TEMPLATE = """<xml>
<Encrypt><![CDATA[%(msg_encrypt)s]]></Encrypt>
<MsgSignature><![CDATA[%(msg_signaturet)s]]></MsgSignature>
<TimeStamp>%(timestamp)s</TimeStamp>
<Nonce><![CDATA[%(nonce)s]]></Nonce>
</xml>"""

    def extract(self, xmltext):
        """提取出xml数据包中的加密消息
        @param xmltext: 待提取的xml字符串
        @return: 提取出的加密消息字符串
        """
        try:
            xml_tree = ET.fromstring(xmltext)
            encrypt  = xml_tree.find("Encrypt")
            touser_name    = xml_tree.find("ToUserName")
            return  WXBizMsgCrypt_OK, encrypt.text, touser_name.text
        except Exception as e:
            #print e
            return  WXBizMsgCrypt_ParseXml_Error,None,None

    def generate(self, encrypt, signature, timestamp, nonce):
        """生成xml消息
        @param encrypt: 加密后的消息密文
        @param signature: 安全签名
        @param timestamp: 时间戳
        @param nonce: 随机字符串
        @return: 生成的xml字符串
        """
        resp_dict = {
                    'msg_encrypt' : encrypt,
                    'msg_signaturet': signature,
                    'timestamp'    : timestamp,
                    'nonce'        : nonce,
                     }
        resp_xml = self.AES_TEXT_RESPONSE_TEMPLATE % resp_dict
        return resp_xml


class PKCS7Encoder():
    """提供基于PKCS7算法的加解密接口"""

    block_size = 32
    def encode(self, text):
        """ 对需要加密的明文进行填充补位
        @param text: 需要进行填充补位操作的明文
        @return: 补齐明文字符串
        """
        text_length = len(text)
        # 计算需要填充的位数
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        # 获得补位所用的字符（兼容 bytes 与 str）
        if isinstance(text, bytes):
            pad = bytes([amount_to_pad])
            return text + pad * amount_to_pad
        else:
            pad = chr(amount_to_pad)
            return text + pad * amount_to_pad

    def decode(self, decrypted):
        """删除解密后明文的补位字符
        @param decrypted: 解密后的明文
        @return: 删除补位字符后的明文
        """
        # 兼容 bytes 与 str 的补位去除
        if isinstance(decrypted, bytes):
            pad = decrypted[-1]
        else:
            pad = ord(decrypted[-1])
        if pad<1 or pad >32:
            pad = 0
        return decrypted[:-pad]


class Prpcrypt(object):
    """提供接收和推送给公众平台消息的加解密接口"""

    def __init__(self,key):
        #self.key = base64.b64decode(key+"=")
        self.key = key
        # 使用 key 的前 16 字节作为 CBC 的 IV（与旧实现保持一致）
        self.iv = self.key[:16]


    def encrypt(self,text,appid):
        """对明文进行加密
        @param text: 需要加密的明文
        @return: 加密得到的字符串
        """
        # 16位随机字符串添加到明文开头
        # 保证 text 与 appid 为字节串
        if isinstance(text, str):
            text = text.encode("utf-8")
        if isinstance(appid, str):
            appid = appid.encode("utf-8")
        text = self.get_random_str() + struct.pack("I",socket.htonl(len(text))) + text + appid
        # 使用自定义的填充方式对明文进行补位填充
        pkcs7 = PKCS7Encoder()
        text = pkcs7.encode(text)
        # 加密（使用 cryptography 实现 AES-CBC）
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv))
        encryptor = cipher.encryptor()
        try:
            ciphertext = encryptor.update(text) + encryptor.finalize()
            # 使用BASE64对加密后的字符串进行编码，返回字符串以便后续处理
            return WXBizMsgCrypt_OK, base64.b64encode(ciphertext).decode("utf-8")
        except Exception as e:
            #print e
            return  WXBizMsgCrypt_EncryptAES_Error,None

    def decrypt(self,text,appid):
        """对解密后的明文进行补位删除
        @param text: 密文
        @return: 删除填充补位后的明文
        """
        try:
            # 保证 appid 为字节串
            if isinstance(appid, str):
                appid = appid.encode("utf-8")
            # 使用BASE64对密文进行解码，然后AES-CBC解密（cryptography）
            cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv))
            decryptor = cipher.decryptor()
            plain_text  = decryptor.update(base64.b64decode(text)) + decryptor.finalize()
        except Exception as e:
            #print e
            return  WXBizMsgCrypt_DecryptAES_Error,None
        try:
            pad = plain_text[-1]
            # 去掉补位字符串
            #pkcs7 = PKCS7Encoder()
            #plain_text = pkcs7.encode(plain_text)
            # 去除16位随机字符串
            content = plain_text[16:-pad]
            xml_len = socket.ntohl(struct.unpack("I",content[ : 4])[0])
            xml_content = content[4 : xml_len+4]
            from_appid = content[xml_len+4:]
        except Exception as e:
            #print e
            return  WXBizMsgCrypt_IllegalBuffer,None
        if  from_appid != appid:
            return WXBizMsgCrypt_ValidateAppid_Error,None
        return 0,xml_content

    def get_random_str(self):
        """ 随机生成16位字符串
        @return: 16位字符串
        """
        rule = string.ascii_letters + string.digits
        s = "".join(random.sample(rule, 16))
        return s.encode("utf-8")

class WXBizMsgCrypt(object):
    #构造函数
    #@param sToken: 公众平台上，开发者设置的Token
    # @param sEncodingAESKey: 公众平台上，开发者设置的EncodingAESKey
    # @param sAppId: 企业号的AppId
    def __init__(self,sToken,sEncodingAESKey,sAppId):
        try:
            self.key = base64.b64decode(sEncodingAESKey+"=")
            assert len(self.key) == 32
        except:
            throw_exception("[error]: EncodingAESKey unvalid !", FormatException)
           #return WXBizMsgCrypt_IllegalAesKey)
        self.token = sToken
        self.appid = sAppId

    def EncryptMsg(self, sReplyMsg, sNonce, timestamp = None):
        #将公众号回复用户的消息加密打包
        #@param sReplyMsg: 企业号待回复用户的消息，xml格式的字符串
        #@param sTimeStamp: 时间戳，可以自己生成，也可以用URL参数的timestamp,如为None则自动用当前时间
        #@param sNonce: 随机串，可以自己生成，也可以用URL参数的nonce
        #sEncryptMsg: 加密后的可以直接回复用户的密文，包括msg_signature, timestamp, nonce, encrypt的xml格式的字符串,
        #return：成功0，sEncryptMsg,失败返回对应的错误码None
        pc = Prpcrypt(self.key)
        ret,encrypt = pc.encrypt(sReplyMsg, self.appid)
        if ret != 0:
            return ret,None
        if timestamp is None:
            timestamp = str(int(time.time()))
        # 生成安全签名
        sha1 = SHA1()
        ret,signature = sha1.getSHA1(self.token, timestamp, sNonce, encrypt)
        if ret != 0:
            return ret,None
        xmlParse = XMLParse()
        return ret,xmlParse.generate(encrypt, signature, timestamp, sNonce)

    def DecryptMsg(self, sPostData, sMsgSignature, sTimeStamp, sNonce):
        # 检验消息的真实性，并且获取解密后的明文
        # @param sMsgSignature: 签名串，对应URL参数的msg_signature
        # @param sTimeStamp: 时间戳，对应URL参数的timestamp
        # @param sNonce: 随机串，对应URL参数的nonce
        # @param sPostData: 密文，对应POST请求的数据
        #  xml_content: 解密后的原文，当return返回0时有效
        # @return: 成功0，失败返回对应的错误码
         # 验证安全签名
        xmlParse = XMLParse()
        ret,encrypt,touser_name = xmlParse.extract(sPostData)
        if ret != 0:
            return ret, None
        sha1 = SHA1()
        ret,signature = sha1.getSHA1(self.token, sTimeStamp, sNonce, encrypt)
        if ret  != 0:
            return ret, None
        if not signature == sMsgSignature:
            return WXBizMsgCrypt_ValidateSignature_Error, None
        pc = Prpcrypt(self.key)
        ret,xml_content = pc.decrypt(encrypt,self.appid)
        return ret,xml_content


# 通过一个对象导出（统一命名空间）
wx = SimpleNamespace(
    receive=SimpleNamespace(
        Msg=WxReceiveMsg,
        Text=WxReceiveTextMsg,
        Image=WxReceiveImageMsg,
        Voice=WxReceiveVoiceMsg,
        Video=WxReceiveVideoMsg,
        ShortVideo=WxReceiveShortVideoMsg,
        Location=WxReceiveLocationMsg,
        Link=WxReceiveLinkMsg,
        parse=wx_parse_receive_xml,
    ),
    reply=SimpleNamespace(
        Msg=WxReplyMsg,
        Text=WxReplyTextMsg,
        Image=WxReplyImageMsg,
        Voice=WxReplyVoiceMsg,
        Video=WxReplyVideoMsg,
        Music=WxReplyMusicMsg,
        News=WxReplyNewsMsg,
    ),
    crypto=SimpleNamespace(
        constants=SimpleNamespace(
            OK=WXBizMsgCrypt_OK,
            ValidateSignatureError=WXBizMsgCrypt_ValidateSignature_Error,
            ParseXmlError=WXBizMsgCrypt_ParseXml_Error,
            ComputeSignatureError=WXBizMsgCrypt_ComputeSignature_Error,
            IllegalAesKey=WXBizMsgCrypt_IllegalAesKey,
            ValidateAppidError=WXBizMsgCrypt_ValidateAppid_Error,
            EncryptAESError=WXBizMsgCrypt_EncryptAES_Error,
            DecryptAESError=WXBizMsgCrypt_DecryptAES_Error,
            IllegalBuffer=WXBizMsgCrypt_IllegalBuffer,
            EncodeBase64Error=WXBizMsgCrypt_EncodeBase64_Error,
            DecodeBase64Error=WXBizMsgCrypt_DecodeBase64_Error,
            GenReturnXmlError=WXBizMsgCrypt_GenReturnXml_Error,
        ),
        FormatException=FormatException,
        throw_exception=throw_exception,
        SHA1=SHA1,
        XMLParse=XMLParse,
        PKCS7Encoder=PKCS7Encoder,
        Prpcrypt=Prpcrypt,
        WXBizMsgCrypt=WXBizMsgCrypt,
    ),
)
