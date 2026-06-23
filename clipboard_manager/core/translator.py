"""翻译服务 — 通过可配置的 HTTP 接口进行文本翻译。"""
import json
import os
import re
import urllib.request
import urllib.error
from typing import Optional


class Translator:
    """使用 JSON 配置文件驱动翻译请求，方便用户更换接口。"""

    _DEFAULT_CONFIG = {
        "url": "https://api.mymemory.translated.net/get",
        "method": "GET",
        "headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        "data": {
            "q": "{text}",
            "langpair": "en|zh-CN",
        },
        "response_path": "responseData.translatedText",
        "timeout": 5,
        "_comment": (
            "━" * 50 + "\n"
            "  翻译接口配置文件\n"
            "  若翻译失效，修改以下字段即可更换接口，无需改动代码。\n"
            "━━" + "━" * 48 + "\n"
            "  url            — 翻译接口地址\n"
            "  method         — 请求方法 (GET / POST)\n"
            "  headers        — HTTP 请求头\n"
            "  data           — 请求参数模板，{text} 会被替换为待翻译文本\n"
            "  response_path  — 翻译结果在返回 JSON 中的路径\n"
            "  timeout        — 请求超时秒数\n"
            "━━" + "━" * 48 + "\n"
            "  当前默认接口: MyMemory (免费，每日 ~1000 字符)\n"
            "  示例 — 换用百度翻译开放平台 (需注册获取 appid+key)：\n"
            "  {\n"
            '    "url": "https://api.fanyi.baidu.com/api/trans/vip/translate",\n'
            '    "method": "POST",\n'
            '    "headers": {"Content-Type": "application/x-www-form-urlencoded"},\n'
            '    "data": {\n'
            '      "q": "{text}",\n'
            '      "from": "en",\n'
            '      "to": "zh",\n'
            '      "appid": "你的appid",\n'
            '      "salt": "123456",\n'
            '      "sign": "你的签名"\n'
            '    },\n'
            '    "response_path": "trans_result[0].dst",\n'
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
                # 去掉 _comment 以免覆盖用户修改后被覆盖的错觉
                saved = json.loads(content)
                # 合并缺失的默认字段
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
        template = self._config.get("data", {})
        params = {}
        for key, val in template.items():
            if isinstance(val, str):
                params[key] = val.replace("{text}", text)
            else:
                params[key] = val
        return params

    def _parse_response(self, raw: str) -> Optional[str]:
        """根据 response_path 从 JSON 中提取翻译结果。"""
        path = self._config.get("response_path", "")
        if not path:
            return None
        try:
            data = json.loads(raw)
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
