"""翻译服务 — 通过可配置的 HTTP 接口进行文本翻译。"""
import hashlib
import json
import os
import random
import re
import urllib.request
import urllib.error
from typing import Optional


class Translator:
    """使用 JSON 配置文件驱动翻译请求，支持内置签名（百度等）。"""

    _DEFAULT_CONFIG = {
        "url": "https://api.fanyi.baidu.com/api/trans/vip/translate",
        "method": "POST",
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        "data": {
            "q": "{text}",
            "from": "en",
            "to": "zh",
            "appid": "你的appid",
            "salt": "{salt}",
        },
        "response_path": "trans_result[0].dst",
        "timeout": 5,
        "sign_type": "baidu",
        "sign_key": "你的密钥",
        "sign_param": "sign",
        "_comment": (
            "━" * 50 + "\n"
            "  翻译接口配置文件\n"
            "  修改以下字段即可更换接口，无需改动代码。\n"
            "━━" + "━" * 48 + "\n"
            "  url          — 翻译接口地址\n"
            "  method       — 请求方法 (GET / POST)\n"
            "  headers      — HTTP 请求头\n"
            "  data         — 请求参数模板\n"
            "                  {text} → 待翻译文本\n"
            "                  {salt} → 自动生成的随机数\n"
            "  response_path — 翻译结果在 JSON 中的路径\n"
            "  timeout      — 请求超时秒数\n"
            "  ---------- 以下为签名配置（可选）----------\n"
            "  sign_type    — 签名类型: \"baidu\" 或 null（无签名）\n"
            "  sign_key     — 签名密钥（百度对应开发者 key）\n"
            "  sign_param   — 签名字段名（百度为 \"sign\"）\n"
            "━━" + "━" * 48 + "\n"
            "  恢复 MyMemory 默认接口：删除此文件后重启应用\n"
            "  （备份文件: translation_config_mymemory_backup.json）\n"
            "━━" + "━" * 48 + "\n"
            "  MyMemory 配置（无签名）:\n"
            '  {\n'
            '    "url": "https://api.mymemory.translated.net/get",\n'
            '    "method": "GET",\n'
            '    "headers": {"User-Agent": "..."},\n'
            '    "data": {"q": "{text}", "langpair": "en|zh-CN"},\n'
            '    "response_path": "responseData.translatedText",\n'
            '    "timeout": 5\n'
            '  }\n'
        ),
    }

    def __init__(self) -> None:
        self._config = self._load_config()

    # ---- public ----

    def translate(self, text: str) -> Optional[str]:
        """翻译文本（英→中），成功返回译文，失败返回 None。"""
        if not text or not text.strip():
            return None

        url = self._config.get("url", "")
        method = self._config.get("method", "POST").upper()
        headers = self._config.get("headers", {})
        timeout = self._config.get("timeout", 5)

        params = self._build_params(text)
        try:
            if method == "POST":
                body = urllib.parse.urlencode(params).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers)
            else:
                query = urllib.parse.urlencode(params)
                sep = "&" if "?" in url else "?"
                req = urllib.request.Request(url + sep + query, headers=headers)

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return self._parse_response(raw)
        except urllib.error.URLError:
            return None
        except Exception:
            return None

    # ---- config ----

    @classmethod
    def get_config_path(cls) -> str:
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "ClipboardManager", "translation_config.json")

    def _load_config(self) -> dict:
        path = self.get_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                saved = json.loads(content)
                merged = dict(self._DEFAULT_CONFIG)
                merged.update(saved)
                return merged
            except Exception:
                pass
        # 首次运行：写入默认配置
        self._save_config(dict(self._DEFAULT_CONFIG))
        return dict(self._DEFAULT_CONFIG)

    def _save_config(self, config: dict) -> None:
        path = self.get_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    # ---- internal ----

    def _build_params(self, text: str) -> dict:
        """构建请求参数，替换占位符并计算签名。"""
        template = self._config.get("data", {})
        salt = str(random.randint(10000, 99999))
        params = {}
        for key, val in template.items():
            if isinstance(val, str):
                params[key] = val.replace("{text}", text).replace("{salt}", salt)
            else:
                params[key] = val

        # 百度签名: md5(appid + q + salt + key)
        sign_type = self._config.get("sign_type")
        if sign_type == "baidu":
            sign_key = self._config.get("sign_key", "")
            sign_param = self._config.get("sign_param", "sign")
            appid = params.get("appid", "")
            q = params.get("q", text)
            sign_str = appid + q + salt + sign_key
            params[sign_param] = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

        return params

    def _parse_response(self, raw: str) -> Optional[str]:
        """根据 response_path 从 JSON 中提取翻译结果。"""
        path = self._config.get("response_path", "")
        if not path:
            return None
        try:
            data = json.loads(raw)
            # 百度错误码检查
            if data and isinstance(data, dict) and "error_code" in data:
                return None
            result = data
            for segment in re.split(r"[\[\].]+", path):
                segment = segment.strip()
                if not segment:
                    continue
                if isinstance(result, list):
                    result = result[int(segment)]
                elif isinstance(result, dict):
                    result = result[segment]
                else:
                    return None
            return str(result) if result else None
        except Exception:
            return None
