/**
 * KairoCore 前端安全加解密工具
 * 
 * 依赖: crypto-js
 * 安装: npm install crypto-js
 * 引入: import { encryptWithDynamicIV, decryptWithDynamicIV } from './crypto_utils';
 */

import CryptoJS from 'crypto-js';

/**
 * 加密函数 (AES-128-CBC + 动态IV + 时间戳)
 * 对应后端 KairoAuth.decrypt_wx_xcx_key 逻辑
 * 
 * @param {string} value - 需要加密的敏感数据 (如 secret)
 * @param {string} keyStr - 16位密钥字符串 (必须与后端配置一致)
 * @returns {string} Base64编码的密文 (包含IV)
 */
export function encryptWithDynamicIV(value, keyStr) {
    try {
        // 1. 构造带时间戳的 Payload
        const payload = JSON.stringify({
            t: Date.now(), // 当前时间戳 (ms)
            v: value       // 实际值
        });

        // 2. 解析密钥 (UTF-8)
        // 注意: 这里假定密钥是普通的 ASCII 字符串
        const key = CryptoJS.enc.Utf8.parse(keyStr);

        // 3. 生成随机 IV (16字节)
        const iv = CryptoJS.lib.WordArray.random(16);

        // 4. 加密
        const encrypted = CryptoJS.AES.encrypt(payload, key, {
            iv: iv,
            mode: CryptoJS.mode.CBC,
            padding: CryptoJS.pad.Pkcs7
        });

        // 5. 拼接 IV + 密文
        // encrypted.ciphertext 是 WordArray
        const combined = iv.concat(encrypted.ciphertext);

        // 6. 返回 Base64
        return CryptoJS.enc.Base64.stringify(combined);
    } catch (error) {
        console.error('加密失败:', error);
        throw error;
    }
}

/**
 * 解密函数 (对应上述加密逻辑)
 * 用于验证或解密后端返回的同格式数据
 * 
 * @param {string} ciphertextBase64 - Base64编码的密文
 * @param {string} keyStr - 16位密钥字符串
 * @returns {string|null} 解密后的原始值 (如果过期或失败返回 null)
 */
export function decryptWithDynamicIV(ciphertextBase64, keyStr) {
    try {
        // 1. Base64 解码
        const rawData = CryptoJS.enc.Base64.parse(ciphertextBase64);
        
        // 2. 提取 IV (前16字节)
        // 16字节 = 4个32位字
        const ivWords = rawData.words.slice(0, 4);
        const iv = CryptoJS.lib.WordArray.create(ivWords, 16);
        
        // 3. 提取密文 (剩余部分)
        const cipherWords = rawData.words.slice(4);
        const cipherSigBytes = rawData.sigBytes - 16;
        const ciphertext = CryptoJS.lib.WordArray.create(cipherWords, cipherSigBytes);

        // 4. 解析密钥
        const key = CryptoJS.enc.Utf8.parse(keyStr);

        // 5. 解密
        const decrypted = CryptoJS.AES.decrypt(
            { ciphertext: ciphertext },
            key, 
            {
                iv: iv,
                mode: CryptoJS.mode.CBC,
                padding: CryptoJS.pad.Pkcs7
            }
        );

        // 6. 转为 UTF-8 字符串并解析 JSON
        const jsonStr = decrypted.toString(CryptoJS.enc.Utf8);
        if (!jsonStr) return null;

        const data = JSON.parse(jsonStr);

        // 7. 校验有效期 (1分钟)
        if (data.t) {
            const now = Date.now();
            if (Math.abs(now - data.t) > 60000) {
                console.warn(`数据已过期: server=${data.t}, client=${now}`);
                return null;
            }
        }

        return data.v;
    } catch (e) {
        console.error("解密失败", e);
        return null;
    }
}
