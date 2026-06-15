#!/usr/bin/env python3
"""OpenCode CLI Validation Script

Validates:
1. Tool calling: Get Beijing current weather
2. Knowledge: List vs Set differences in Python (no garbled/nonsense text)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_opencode(prompt, model, config_path, work_dir, timeout=180):
    """Run opencode in non-interactive mode and capture output."""
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = config_path
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    env["LANG"] = env.get("LANG", "en_US.UTF-8")
    env["LC_ALL"] = env.get("LC_ALL", "en_US.UTF-8")

    cmd = [
        "opencode",
        "run",
        prompt,
        "--model",
        model,
        "--dangerously-skip-permissions",
    ]

    print(f"[INFO] Running: {' '.join(cmd)}")
    print(f"[INFO] Config: {config_path}")
    print(f"[INFO] Work dir: {work_dir}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
            env=env,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        return stdout, stderr + f"\nCommand timed out after {timeout}s", -1
    except Exception as e:
        return "", str(e), -1


def validate_weather_output(output):
    """Validate tool calling output for Beijing weather.

    Checks:
    - Output contains weather-related information (temperature, conditions)
    - Output mentions Beijing
    - Output appears to contain real/current data (not just generic weather description)
    """
    issues = []
    details = {}

    weather_keywords = [
        "天气",
        "温度",
        "气温",
        "晴",
        "阴",
        "雨",
        "雪",
        "风",
        "摄氏",
        "°C",
        "℃",
        "湿度",
        "cloudy",
        "rainy",
        "sunny",
        "wind",
        "weather",
        "temperature",
        "Beijing",
    ]
    found_weather_kws = [kw for kw in weather_keywords if kw in output]
    details["found_weather_keywords"] = found_weather_kws

    if len(found_weather_kws) < 2:
        issues.append(
            f"Output lacks weather-related keywords (found {len(found_weather_kws)}: {found_weather_kws})"
        )

    has_beijing = "北京" in output or "Beijing" in output
    details["mentions_beijing"] = has_beijing
    if not has_beijing:
        issues.append("Output does not mention Beijing (北京/Beijing)")

    temperature_pattern = re.compile(
        r"-?\d{1,3}\s*[°℃C]\s*[FC]?"
        r"|"
        r"[零负]?\d{1,3}[度摄氏]",
    )
    has_temperature = bool(temperature_pattern.search(output))
    details["has_temperature_data"] = has_temperature
    if not has_temperature:
        issues.append("Output does not contain specific temperature data")

    tool_indicators = [
        "webfetch",
        "websearch",
        "bash",
        "curl",
        "http",
        "wttr.in",
        "weatherapi",
        "openweathermap",
        "搜索",
        "查询",
        "获取",
        "调用",
    ]
    found_tool_indicators = [
        kw for kw in tool_indicators if kw.lower() in output.lower()
    ]
    details["tool_indicators"] = found_tool_indicators
    if not found_tool_indicators:
        issues.append(
            "No tool usage indicators found in output (model may not have used tools)"
        )

    if len(output.strip()) < 30:
        issues.append("Output is too short, possibly empty or incomplete")

    return {
        "test_name": "Tool Calling - Beijing Weather",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:1000] if output else "",
    }


def validate_list_set_output(output):
    """Validate knowledge output for list vs set differences in Python.

    Checks:
    - No garbled text (control characters)
    - Contains expected comparison keywords
    - Output is coherent (no excessive repetition / nonsense)
    - Output is reasonably long
    """
    issues = []
    details = {}

    garbled_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    garbled_matches = garbled_pattern.findall(output)
    details["garbled_chars_count"] = len(garbled_matches)
    if garbled_matches:
        issues.append(
            f"Output contains {len(garbled_matches)} garbled/control characters"
        )

    encoding_issues = re.compile(r"(\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2})")
    encoding_matches = encoding_issues.findall(output)
    if len(encoding_matches) > 5:
        issues.append(
            f"Output contains {len(encoding_matches)} Unicode escape sequences (possible encoding issues)"
        )

    expected_keywords = [
        "列表",
        "集合",
        "有序",
        "无序",
        "可变",
        "重复",
        "唯一",
        "不重复",
        "索引",
        "方括号",
        "花括号",
        "元素",
        "list",
        "set",
        "ordered",
        "unordered",
        "mutable",
        "duplicate",
        "unique",
        "index",
        "bracket",
        "[]",
        "{}",
    ]
    found_keywords = [kw for kw in expected_keywords if kw in output]
    details["found_keywords"] = found_keywords
    details["found_keyword_count"] = len(found_keywords)
    if len(found_keywords) < 3:
        issues.append(
            f"Output lacks expected comparison keywords (found {len(found_keywords)}: {found_keywords})"
        )

    if len(output.strip()) < 50:
        issues.append("Output is too short, possibly incomplete")

    words = output.split()
    if len(words) > 10:
        unique_ratio = len(set(words)) / len(words)
        details["unique_word_ratio"] = round(unique_ratio, 3)
        if unique_ratio < 0.3:
            issues.append(
                f"Output has excessive repetition (unique ratio: {unique_ratio:.2f}), possibly nonsensical"
            )

    max_repeat = 1
    current_repeat = 1
    for i in range(1, len(words)):
        if words[i] == words[i - 1]:
            current_repeat += 1
            max_repeat = max(max_repeat, current_repeat)
        else:
            current_repeat = 1
    details["max_consecutive_repeat"] = max_repeat
    if max_repeat > 5:
        issues.append(
            f"Output has consecutive word repetition (max {max_repeat} times), possibly nonsensical"
        )

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", output)
    mixed_nonsense = re.compile(r"([\u4e00-\u9fff]{1,2}[a-zA-Z]{1,2}){3,}")
    if mixed_nonsense.search(output):
        issues.append("Output contains mixed Chinese-English nonsense patterns")

    return {
        "test_name": "Knowledge - List vs Set in Python",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:1000] if output else "",
    }


def generate_markdown_report(results, output_dir, params):
    """Generate markdown report."""
    summary = results["summary"]
    status_icon = "PASSED" if summary["failed"] == 0 else "FAILED"

    report = f"""# OpenCode CLI Validation Report

**Timestamp:** {results["timestamp"]}
**Model:** {results["model"]}
**Base URL:** {params.get("base_url", "N/A")}
**Infra:** {params.get("infra", "N/A")}
**Chip:** {params.get("chip", "N/A")}
**PD Mode:** {params.get("pd", "N/A")}
**Overall Status:** {status_icon}

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {summary["total"]} |
| Passed | {summary["passed"]} |
| Failed | {summary["failed"]} |
| Pass Rate | {summary["pass_rate"]} |

## Test Details

"""
    for test in results["tests"]:
        status = "PASSED" if test["passed"] else "FAILED"
        report += f"### {test['test_name']} - {status}\n\n"
        if test["issues"]:
            report += "**Issues:**\n"
            for issue in test["issues"]:
                report += f"- {issue}\n"
            report += "\n"
        if test.get("details"):
            report += "**Validation Details:**\n"
            for key, value in test["details"].items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value) if value else "none"
                report += f"- {key}: {value}\n"
            report += "\n"
        report += f"**Output Preview:**\n```\n{test['output_preview']}\n```\n\n---\n\n"

    report_file = os.path.join(output_dir, "validation_report.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[INFO] Markdown report saved to: {report_file}")
    return report_file


def main():
    parser = argparse.ArgumentParser(description="OpenCode CLI Validation Script")
    parser.add_argument(
        "--model",
        required=True,
        help="Model name in provider/model format (e.g., custom-openai/kimi-k2.5)",
    )
    parser.add_argument(
        "--config-path",
        required=True,
        help="Path to opencode config file inside container",
    )
    parser.add_argument(
        "--work-dir", required=True, help="Working directory for opencode"
    )
    parser.add_argument(
        "--timeout", type=int, default=180, help="Timeout per test in seconds"
    )
    parser.add_argument(
        "--output-dir", default="./results", help="Output directory for results"
    )
    parser.add_argument(
        "--base-url", default="", help="Base URL of LLM API (for report)"
    )
    parser.add_argument("--infra", default="", help="Inference framework (for report)")
    parser.add_argument("--chip", default="", help="Chip platform (for report)")
    parser.add_argument("--pd", default="", help="PD mode (for report)")
    parser.add_argument("--tester", default="", help="Tester name (for report)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    params = {
        "base_url": args.base_url,
        "infra": args.infra,
        "chip": args.chip,
        "pd": args.pd,
        "tester": args.tester,
    }

    results = {
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "tests": [],
    }

    # ============================================================
    # Test 1: Tool Calling - Beijing Weather
    # ============================================================
    print("=" * 60)
    print("Test 1: Tool Calling - Getting Beijing Current Weather")
    print("=" * 60)

    weather_prompt = "请获取北京市当前的天气情况，告诉我现在的温度和天气状况。请使用工具来获取实时天气信息。"
    stdout, stderr, returncode = run_opencode(
        weather_prompt,
        args.model,
        args.config_path,
        args.work_dir,
        args.timeout,
    )

    combined_output = stdout
    if stderr:
        print(f"[WARN] stderr: {stderr[:500]}")
        combined_output += "\n" + stderr

    weather_result = validate_weather_output(combined_output)
    weather_result["returncode"] = returncode
    weather_result["stderr_preview"] = stderr[:500] if stderr else ""
    results["tests"].append(weather_result)

    status = "PASSED" if weather_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if weather_result["issues"]:
        for issue in weather_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(args.output_dir, "weather_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 2: Knowledge - List vs Set in Python
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 2: Knowledge - List vs Set in Python")
    print("=" * 60)

    list_set_prompt = "请详细列出Python语言中列表(list)和集合(set)的区别，包括定义、特性、使用场景等。"
    stdout, stderr, returncode = run_opencode(
        list_set_prompt,
        args.model,
        args.config_path,
        args.work_dir,
        args.timeout,
    )

    combined_output = stdout
    if stderr:
        print(f"[WARN] stderr: {stderr[:500]}")
        combined_output += "\n" + stderr

    list_set_result = validate_list_set_output(combined_output)
    list_set_result["returncode"] = returncode
    list_set_result["stderr_preview"] = stderr[:500] if stderr else ""
    results["tests"].append(list_set_result)

    status = "PASSED" if list_set_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if list_set_result["issues"]:
        for issue in list_set_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(args.output_dir, "list_set_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Summary
    # ============================================================
    total = len(results["tests"])
    passed = sum(1 for t in results["tests"] if t["passed"])
    results["summary"] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": f"{passed / total * 100:.1f}%",
    }

    print("\n" + "=" * 60)
    print(f"Summary: {passed}/{total} tests passed ({results['summary']['pass_rate']})")
    print("=" * 60)

    results_file = os.path.join(args.output_dir, "validation_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Results saved to: {results_file}")

    report_file = generate_markdown_report(results, args.output_dir, params)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
