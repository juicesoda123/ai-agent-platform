# Day 26 — PII 脱敏：结构化隐私检测

> Phase 6：生产化部署  |  预计用时：35 分钟  |  2026-05-08

---

## 今日目标

1. 理解 PII 脱敏和 OutputGuard 的分工——安全红线 vs 隐私合规
2. 掌握 PIIScanner 的 10 种内置检测规则 + 自定义扩展
3. 理解 Luhn 算法为什么能过滤假卡号
4. 产出：`agent_platform/pii.py`，32 个测试全过

---

## 一、概念对齐：PII 脱敏 vs OutputGuard

D1 的 OutputGuard 是**安全底线**——API Key 泄露了，别人能调你的接口、花你的钱。所以 OutputGuard 用 `redact/block` 模式，发现敏感信息直接处理。

PII 脱敏是**隐私合规**——用户姓名、手机、地址这些信息在日志/数据库/API 响应里出现，GDPR 和个保法要求你有能力检测和脱敏。这些信息本身不危险，但不脱敏就违规。

```
OutputGuard:  API Key → block/redact（安全红线）
PII Scanner:  姓名/地址/卡号 → 检测+报告+打码（隐私合规）
```

**两者可以串在 GuardrailRunner 里一起用。**

---

## 二、PIIScanner 架构

```
PIIScanner
  ├── 10 种内置 PII 类型
  │   ├── 金融：信用卡(Luhn) / 银行卡
  │   ├── 网络：IPv4 / IPv6
  │   ├── 联系：手机 / 邮箱 / 身份证
  │   ├── 个人：中文姓名 / 年龄性别
  │   └── 位置：详细地址
  ├── 每种类型有一个 pattern + mask + 可选 detector
  └── scan() → PIIScanResult (original, sanitized, matches[])
```

### PII 类型结构

```python
PIIType(
    name="CREDIT_CARD",            # 内部标识
    label="信用卡号",               # 中文标签
    pattern=re.compile(...),       # 正则初筛
    mask=_mask_keep_last(4),       # 脱敏函数：保留后 4 位
    detector=lambda s: luhn_check(s),  # 二次校验：Luhn 算法
    severity="high",               # 严重程度：low/medium/high
)
```

**关键设计决策——为什么需要 detector？**

正则只能做模式匹配。信用卡号 `4111-1111-1111-1111` 和 `1234-5678-9012-3456` 正则看起来一样，但只有前者能通过 Luhn 算法校验。不用 `detector` 二次过滤，假卡号也会被标记为 PII，产生噪音。

### Luhn 算法原理

信用卡号最后一位是校验位。Luhn 算法从右往左，偶数位翻倍，如果翻倍后 ≥10 则减 9，求和。能被 10 整除 = 合法卡号。

```
卡号: 4111 1111 1111 1111
从右往左: 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 4
翻倍偶数位: 1 2 1 2 1 2 1 2 1 2 1 2 1 2 1 8
和 = 30 → 30 % 10 = 0 → 合法
```

---

## 三、使用方式

### 一键扫描

```python
from agent_platform.pii import PIIScanner

scanner = PIIScanner()
result = scanner.scan("姓名: 张三, 手机: 13812345678")

print(result.summary)      # "中文姓名x1, 手机号x1"
print(result.sanitized)    # "姓名: 张*, 手机: 138****5678"
print(result.found_count)  # 2
```

### 生成报告

```python
print(scanner.scan_and_report(text))
# PII 扫描报告: 发现 2 处 (高危 0)
# 摘要: 中文姓名x1, 手机号x1
# ---
# 脱敏后: 姓名: 张*, 手机: 138****5678
```

### 自定义 PII 类型

```python
from agent_platform.pii import PIIType, PIIScanner
import re

scanner = PIIScanner([
    PIIType(
        name="EMPLOYEE_ID",
        label="工号",
        pattern=re.compile(r"EMP\d{6}"),
        mask=lambda s: "EMP******",
        severity="low",
    ),
])
```

---

## 四、验收标准

```bash
python agent-platform/examples/test_pii.py
```

```
RESULTS: 32 passed, 0 failed
ALL PASSED
```

| 测试组 | 测试数 | 覆盖点 |
|--------|--------|--------|
| 信用卡号 | 4 | VISA + 带连字符 + Luhn 过滤假号 + 保留后 4 位 |
| 银行卡号 | 2 | 检测 + 脱敏 |
| IP 地址 | 3 | IPv4 多地址 + 脱敏 + IPv6 |
| 手机+邮箱 | 4 | 检测 + 各自脱敏策略 |
| 身份证 | 2 | 检测 + 保留后 4 位 |
| 中文姓名 | 3 | 单名 + 双字名 + 连续姓名 |
| 地址 | 2 | 省市区 + 详细到门牌号 |
| 混合文本 | 4 | 5 种 PII 同时出现 |
| 边界 | 3 | 空文本 / 无PII / 短数字 |
| scan_and_report | 3 | 标题/摘要/脱敏 |
| 自定义类型 | 2 | 扩展 + 脱敏 |

---

## 五、与 Guardrails 的集成

```python
from agent_platform.guardrails import GuardrailRunner, OutputGuard
from agent_platform.pii import PIIScanner

runner = GuardrailRunner()
runner.add_output(OutputGuard(action="redact"))  # 安全红线

pii = PIIScanner()  # 隐私合规

# Agent 返回后
guard_result = runner.run_output(agent_reply)
pii_result = pii.scan(guard_result.data)
final_output = pii_result.sanitized
```

---

## 六、脱敏策略速查

| PII 类型 | 脱敏方式 | 示例 |
|---------|---------|------|
| 信用卡号 | 保留后 4 位 | `************1111` |
| 银行卡号 | 保留后 4 位 | `************7890` |
| IPv4 | 隐藏后两段 | `192.168.*.*` |
| IPv6 | 隐藏后半 | `2001:***` |
| 手机号 | 中间 4 位打码 | `138****5678` |
| 邮箱 | 名前打码 | `t***@example.com` |
| 身份证 | 保留后 4 位 | `**************1234` |
| 中文姓名 | 保留姓 | `张*` / `王**` |
| 地址 | 保留前 3 字 | `北京市****` |
