"""验证 PII 检测与脱敏 —— 纯逻辑测试，不需要 API Key。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.pii import PIIScanner, BUILTIN_PII_TYPES

passed = 0
failed = 0


def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} — {detail}")


scanner = PIIScanner()

# ============================================================
# 1. 信用卡号（Luhn 算法校验）
# ============================================================
print("=== 1. 信用卡号 ===")

# 合法 VISA 测试号: 4111 1111 1111 1111
r = scanner.scan("我的卡号是 4111111111111111")
test("VISA 卡号检测", r.found_count >= 1 and "信用卡号" in r.summary, r.summary)
test("卡号已脱敏", "4111111111111111" not in r.sanitized and "****" in r.sanitized, r.sanitized)

# 格式化的卡号
r = scanner.scan("卡号: 5500-0000-0000-0004")
test("带连字符卡号", r.found_count >= 1 and "信用卡号" in r.summary, r.summary)

# 假卡号（通不过 Luhn）
r = scanner.scan("卡号: 1234-5678-9012-3456")
test("假卡号被 Luhn 过滤", "信用卡号" not in r.summary, r.summary)


# ============================================================
# 2. 银行卡号
# ============================================================
print("\n=== 2. 银行卡号 ===")

r = scanner.scan("转账到 6222021234567890123")
test("银行卡检测", r.found_count >= 1 and "银行卡号" in r.summary, r.summary)
test("银行卡脱敏保留后 4 位", r.sanitized.count("*") > 5 and r.sanitized[-4:].isdigit(), r.sanitized)


# ============================================================
# 3. IP 地址
# ============================================================
print("\n=== 3. IP 地址 ===")

r = scanner.scan("服务器地址: 192.168.1.100 和 10.0.0.1")
test("IPv4 检测", r.found_count >= 2, f"found {r.found_count}")
test("IP 脱敏", "192.168" in r.sanitized and "1.100" not in r.sanitized, r.sanitized)

r = scanner.scan("IPv6: 2001:0db8:85a3:0000:0000:8a2e:0370:7334")
test("IPv6 检测", r.found_count >= 1, f"found {r.found_count}")


# ============================================================
# 4. 手机号 + 邮箱
# ============================================================
print("\n=== 4. 手机号 + 邮箱 ===")

r = scanner.scan("联系: 13812345678, email: test@example.com")
test("手机号检测", "手机号" in r.summary)
test("邮箱检测", "邮箱" in r.summary)
test("手机脱敏", "138****5678" in r.sanitized, r.sanitized)
test("邮箱脱敏", "test@example.com" not in r.sanitized, r.sanitized)


# ============================================================
# 5. 身份证
# ============================================================
print("\n=== 5. 身份证 ===")

r = scanner.scan("身份证 110101199001011234 请核实")
test("身份证检测", r.found_count >= 1 and "身份证号" in r.summary, r.summary)
test("身份证脱敏保留后 4 位", r.sanitized[-5:-1] == "1234" or "****" in r.sanitized, r.sanitized)


# ============================================================
# 6. 中文姓名
# ============================================================
print("\n=== 6. 中文姓名 ===")

r = scanner.scan("申请人：张三，推荐人：李四")
test("中文姓名检测", "中文姓名" in r.summary, r.summary)
test("姓名脱敏", "张三" not in r.sanitized and "李四" not in r.sanitized, r.sanitized)

r = scanner.scan("王小明和陈大文一起提交")
test("双字名检测", "中文姓名" in r.summary, r.summary)


# ============================================================
# 7. 地址
# ============================================================
print("\n=== 7. 地址 ===")

r = scanner.scan("收货地址：北京市朝阳区三里屯路18号")
test("地址检测", r.found_count >= 1 and "地址" in r.summary, r.summary)

r = scanner.scan("广东省深圳市南山区科技园路1号B栋201室")
test("详细地址检测", r.found_count >= 1, f"found {r.found_count}")


# ============================================================
# 8. 混合文本
# ============================================================
print("\n=== 8. 混合文本 ===")

mixed = """
用户信息：
姓名：刘伟
手机：13900001111
邮箱：liuwei@company.com
身份证：32010619850615421X
银行卡：6217001234567890
地址：上海市浦东新区张江路88号
"""
r = scanner.scan(mixed)
test("混合文本检测 ≥5 种 PII", r.found_count >= 5, f"found {r.found_count}: {r.summary}")
test("脱敏后不含原始手机", "13900001111" not in r.sanitized)
test("脱敏后不含原始邮箱", "liuwei@company.com" not in r.sanitized)
test("脱敏后不含原始身份证", "32010619850615421X" not in r.sanitized)


# ============================================================
# 9. 边界情况
# ============================================================
print("\n=== 9. 边界情况 ===")

r = scanner.scan("")
test("空文本", r.found_count == 0 and r.sanitized == "")

r = scanner.scan("今天天气真好")
test("无 PII 文本", r.found_count == 0 and r.summary == "未发现 PII")

r = scanner.scan("12345")  # 太短，不匹配任何规则
test("纯数字但不匹配", r.found_count == 0, r.summary)


# ============================================================
# 10. scan_and_report
# ============================================================
print("\n=== 10. scan_and_report ===")

report = scanner.scan_and_report("姓名: 赵六, 手机: 13800138000")
test("报告包含标题", "PII 扫描报告" in report)
test("报告包含摘要", "手机号" in report and "中文姓名" in report)
test("报告包含脱敏后文本", "赵六" not in report and "13800138000" not in report)

# ============================================================
# 11. 自定义 PII 类型
# ============================================================
print("\n=== 11. 自定义 PII 类型 ===")

from agent_platform.pii import PIIType, PIIScanner
import re

custom_scanner = PIIScanner([
    PIIType(
        name="EMPLOYEE_ID",
        label="工号",
        pattern=re.compile(r"\bEMP\d{6}\b"),
        mask=lambda s: "EMP******",
        severity="low",
    ),
])
r = custom_scanner.scan("我的工号是 EMP123456")
test("自定义 PII 检测", r.found_count == 1 and "工号" in r.summary, r.summary)
test("自定义 PII 脱敏", "EMP123456" not in r.sanitized and "EMP******" in r.sanitized, r.sanitized)


# ============================================================
print(f"\n{'='*40}")
print(f"RESULTS: {passed} passed, {failed} failed (total {passed + failed})")
print(f"{'ALL PASSED' if failed == 0 else 'SOME FAILED'}")
