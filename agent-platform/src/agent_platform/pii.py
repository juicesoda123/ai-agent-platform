"""PII 检测与脱敏 —— 结构化隐私信息识别。

与 OutputGuard 的区别：
  OutputGuard: 安全红线——挡 API Key / Token (redact/block)
  PII 模块:    隐私合规——检测+脱敏姓名/卡号/地址等 (report + mask)

内置 10 种 PII 类型，每种有独立的检测规则和脱敏策略。
"""

import re
from dataclasses import dataclass, field
from typing import Callable


# ============================================================
# PII 类型定义
# ============================================================

@dataclass
class PIIType:
    name: str           # 类型名: "CREDIT_CARD"
    label: str          # 中文标签: "信用卡号"
    pattern: re.Pattern | None  # 正则（None 表示用自定义 detector）
    mask: Callable[[str], str]  # 脱敏函数
    detector: Callable[[str], bool] | None = None  # 自定义检测器（用于需要算法校验的类型）
    severity: str = "medium"  # low / medium / high


def _mask_keep_last(n: int) -> Callable[[str], str]:
    """保留最后 n 位的脱敏函数。"""
    def _mask(s: str) -> str:
        clean = re.sub(r"[-\s]", "", s)
        if len(clean) <= n:
            return "*" * len(s)
        visible = clean[-n:]
        return "*" * (len(clean) - n) + visible
    return _mask


def _mask_stars(_: str) -> str:
    return "****"


def _mask_email(s: str) -> str:
    parts = s.split("@")
    if len(parts) != 2:
        return "***@***"
    name, domain = parts
    return (name[0] if name else "*") + "***@" + domain


# ============================================================
# Luhn 算法 —— 信用卡号校验
# ============================================================

def _luhn_check(s: str) -> bool:
    digits = re.sub(r"[-\s]", "", s)
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# ============================================================
# 内置 PII 类型（10 种）
# ============================================================

BUILTIN_PII_TYPES: list[PIIType] = [
    # --- 金融类 ---
    PIIType(
        name="CREDIT_CARD",
        label="信用卡号",
        pattern=re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        mask=_mask_keep_last(4),
        detector=lambda s: _luhn_check(s),
        severity="high",
    ),
    PIIType(
        name="BANK_CARD",
        label="银行卡号",
        pattern=re.compile(r"\b(?:62|60|9[0-9])\d{14,17}\b"),
        mask=_mask_keep_last(4),
        severity="high",
    ),
    # --- 网络类 ---
    PIIType(
        name="IPV4",
        label="IPv4 地址",
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        mask=lambda s: ".".join(s.split(".")[:2] + ["*.*"]),
        severity="low",
    ),
    PIIType(
        name="IPV6",
        label="IPv6 地址",
        pattern=re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"
        ),
        mask=lambda s: s.split(":")[0] + ":***",
        severity="low",
    ),
    # --- 联系类 ---
    PIIType(
        name="PHONE",
        label="手机号",
        pattern=re.compile(r"\b1[3-9]\d{9}\b"),
        mask=lambda s: s[:3] + "****" + s[-4:],
        severity="medium",
    ),
    PIIType(
        name="EMAIL",
        label="邮箱",
        pattern=re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ),
        mask=_mask_email,
        severity="medium",
    ),
    PIIType(
        name="ID_CARD",
        label="身份证号",
        pattern=re.compile(
            r"\b\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])"
            r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
        ),
        mask=_mask_keep_last(4),
        severity="high",
    ),
    # --- 个人类 ---
    PIIType(
        name="CHINESE_NAME",
        label="中文姓名",
        pattern=re.compile(
            r"(?<![a-zA-Z])(?:王|李|张|刘|陈|杨|黄|赵|周|吴|徐|孙|马|朱|胡|郭|何|高|林|罗|郑|梁|谢|宋|唐|许|韩|冯|邓|曹|彭|曾|肖|田"
            r"|董|袁|潘|于|蒋|蔡|余|杜|叶|程|苏|魏|吕|丁|任|沈|姚|卢|姜|崔|钟|谭|陆|汪|范|金|石|廖|贾|夏|韦|傅|方|白|邹|孟"
            r"|熊|秦|邱|江|尹|薛|闫|段|雷|侯|龙|史|陶|黎|贺|顾|毛|郝|龚|邵|万|钱|严|覃|武|戴|莫|孔|向|汤|温|康|施|文|牛|樊"
            r")[^\x00-\x1f\x7f]{1,2}(?![a-zA-Z])"
        ),
        mask=lambda s: s[0] + "*" * (len(s) - 1) if len(s) > 1 else "*",
        severity="medium",
    ),
    PIIType(
        name="AGE_GENDER",
        label="年龄/性别",
        pattern=re.compile(
            r"(?:(?:年龄|岁数)[：:]\s*\d{1,3}|(?:性别)[：:]\s*[男女])"
        ),
        mask=_mask_stars,
        severity="low",
    ),
    # --- 地址类 ---
    PIIType(
        name="ADDRESS",
        label="详细地址",
        pattern=re.compile(
            r"(?:省|市|区|县|镇|乡|村|路|街|巷|号|栋|单元|室|楼)"
            r"[^\n]{0,15}(?:省|市|区|县|镇|乡|村|路|街|巷|号|栋|单元|室|楼)"
        ),
        mask=lambda s: s[:3] + "****" if len(s) > 3 else "****",
        severity="medium",
    ),
]


# ============================================================
# PII 扫描结果
# ============================================================

@dataclass
class PIIMatch:
    pii_type: str      # PII 类型名
    label: str          # 中文标签
    original: str       # 原始文本
    masked: str         # 脱敏后
    position: int       # 在文本中的位置
    severity: str       # 严重程度


@dataclass
class PIIScanResult:
    original: str
    sanitized: str
    matches: list[PIIMatch] = field(default_factory=list)

    @property
    def found_count(self) -> int:
        return len(self.matches)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for m in self.matches if m.severity == "high")

    @property
    def summary(self) -> str:
        if not self.matches:
            return "未发现 PII"
        labels = {}
        for m in self.matches:
            labels[m.label] = labels.get(m.label, 0) + 1
        return ", ".join(f"{k}x{v}" for k, v in labels.items())


# ============================================================
# PII Scanner
# ============================================================

class PIIScanner:
    """PII 扫描器 —— 检测 + 脱敏 + 生成报告。"""

    def __init__(self, pii_types: list[PIIType] | None = None):
        self._types = pii_types or BUILTIN_PII_TYPES

    @property
    def supported_types(self) -> list[str]:
        return [t.name for t in self._types]

    def scan(self, text: str) -> PIIScanResult:
        matches: list[PIIMatch] = []
        sanitized = text

        for pii in self._types:
            if pii.pattern is None:
                continue
            for m in pii.pattern.finditer(text):
                candidate = m.group()
                # 自定义检测器二次校验
                if pii.detector and not pii.detector(candidate):
                    continue
                matches.append(PIIMatch(
                    pii_type=pii.name,
                    label=pii.label,
                    original=candidate,
                    masked=pii.mask(candidate),
                    position=m.start(),
                    severity=pii.severity,
                ))

        # 按位置从后往前替换，避免位置偏移
        for m in sorted(matches, key=lambda x: x.position, reverse=True):
            sanitized = sanitized[:m.position] + m.masked + sanitized[m.position + len(m.original):]

        return PIIScanResult(original=text, sanitized=sanitized, matches=matches)

    def scan_and_report(self, text: str) -> str:
        """一键扫描 + 脱敏 + 生成人类可读报告。"""
        result = self.scan(text)
        lines = [
            f"PII 扫描报告: 发现 {result.found_count} 处 (高危 {result.high_severity_count})",
            f"摘要: {result.summary}",
            "---",
            f"脱敏后: {result.sanitized}",
        ]
        return "\n".join(lines)
