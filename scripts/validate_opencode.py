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
import urllib.request
import urllib.error
from datetime import datetime


def check_api_connectivity(base_url):
    """Check if the LLM API is reachable."""
    url = f"{base_url}/v1/models"
    print(f"[INFO] Checking API connectivity: {url}")
    try:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer EMPTY"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"[INFO] API reachable, status={resp.status}")
            print(f"[INFO] /v1/models response (first 500 chars): {body[:500]}")
            return True
    except Exception as e:
        print(f"[ERROR] API not reachable: {e}")
        return False


def check_opencode_config(config_path):
    """Print and validate the opencode config."""
    print(f"[INFO] Checking opencode config: {config_path}")
    try:
        with open(config_path, "r") as f:
            content = f.read()
        print(f"[INFO] Config content:\n{content}")
        config = json.loads(content)
        if "provider" not in config:
            print("[ERROR] No 'provider' key in config")
            return False
        for pid, pconf in config.get("provider", {}).items():
            opts = pconf.get("options", {})
            base = opts.get("baseURL", "")
            print(f"[INFO] Provider '{pid}': baseURL={base}")
            if "{env:" in base:
                env_name = re.search(r"\{env:(\w+)\}", base)
                if env_name:
                    var_name = env_name.group(1)
                    actual = os.environ.get(var_name, "")
                    if actual:
                        resolved = base.replace(f"{{env:{var_name}}}", actual)
                        print(f"[INFO]   Resolved: {resolved}")
                    else:
                        print(f"[ERROR]   Environment variable {var_name} is not set!")
                        return False
        return True
    except Exception as e:
        print(f"[ERROR] Failed to read config: {e}")
        return False


def run_opencode(prompt, model, config_path, work_dir, timeout=300):
    """Run opencode in non-interactive mode and capture output."""
    env = os.environ.copy()
    env["OPENCODE_CONFIG"] = config_path
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    env["LANG"] = env.get("LANG", "en_US.UTF-8")
    env["LC_ALL"] = env.get("LC_ALL", "en_US.UTF-8")
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"

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
    print(f"[INFO] BASE_URL env: {env.get('BASE_URL', '<not set>')}")

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


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?m")
    return ansi_pattern.sub("", text)


def validate_weather_output(output):
    """Validate tool calling output for Beijing weather."""
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
    """Validate knowledge output for list vs set differences in Python."""
    issues = []
    details = {}

    garbled_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    garbled_matches = garbled_pattern.findall(output)
    details["garbled_chars_count"] = len(garbled_matches)
    if garbled_matches:
        issues.append(
            f"Output contains {len(garbled_matches)} garbled/control characters"
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
        help="Model name in provider/model format (e.g., openai/kimi-k2.5)",
    )
    parser.add_argument(
        "--config-path",
        required=True,
        help="Path to opencode.json config file inside container",
    )
    parser.add_argument(
        "--work-dir",
        required=True,
        help="Working directory for opencode",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per test in seconds",
    )
    parser.add_argument(
        "--output-dir",
        default="./results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Base URL of LLM API",
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
    # Pre-flight checks
    # ============================================================
    print("=" * 60)
    print("Pre-flight Checks")
    print("=" * 60)

    config_ok = check_opencode_config(args.config_path)
    if not config_ok:
        print("[ERROR] opencode config check failed, aborting")
        results["tests"] = []
        results["summary"] = {"total": 0, "passed": 0, "failed": 0, "pass_rate": "N/A"}
        results["preflight_error"] = "opencode config check failed"
        with open(
            os.path.join(args.output_dir, "validation_results.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        return 1

    if args.base_url:
        api_ok = check_api_connectivity(args.base_url)
        if not api_ok:
            print("[WARN] API connectivity check failed, proceeding anyway...")

    # ============================================================
    # Test 0: Smoke test - simple prompt to verify opencode run works
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 0: Smoke Test - Simple greeting")
    print("=" * 60)

    smoke_prompt = "Say hello in one sentence."
    stdout, stderr, returncode = run_opencode(
        smoke_prompt,
        args.model,
        args.config_path,
        args.work_dir,
        timeout=120,
    )
    stdout_clean = strip_ansi(stdout)
    stderr_clean = strip_ansi(stderr)

    print(f"[INFO] Smoke test returncode: {returncode}")
    print(f"[INFO] Smoke test stdout (first 500 chars): {stdout_clean[:500]}")
    if stderr_clean.strip():
        print(f"[INFO] Smoke test stderr (first 500 chars): {stderr_clean[:500]}")

    if returncode != 0 or len(stdout_clean.strip()) < 5:
        print(f"[ERROR] Smoke test failed! opencode run is not working properly.")
        print(f"[ERROR] Cannot proceed with further tests.")
        results["tests"].append(
            {
                "test_name": "Smoke Test",
                "passed": False,
                "issues": [
                    f"opencode run returned code {returncode}, stdout too short or empty"
                ],
                "details": {
                    "returncode": returncode,
                    "stdout_preview": stdout_clean[:500],
                    "stderr_preview": stderr_clean[:500],
                },
                "output_preview": stdout_clean[:1000],
            }
        )
        total = 1
        passed = 0
        results["summary"] = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed / total * 100:.1f}%",
        }
        with open(
            os.path.join(args.output_dir, "validation_results.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        with open(
            os.path.join(args.output_dir, "smoke_output.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(
                f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
            )
        return 1

    print("[INFO] Smoke test passed, proceeding with full tests...")

    # ============================================================
    # Test 1: Tool Calling - Beijing Weather
    # ============================================================
    print("\n" + "=" * 60)
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

    stdout_clean = strip_ansi(stdout)
    stderr_clean = strip_ansi(stderr)
    combined_output = stdout_clean
    if stderr_clean.strip():
        print(f"[WARN] stderr: {stderr_clean[:500]}")
        combined_output += "\n" + stderr_clean

    weather_result = validate_weather_output(combined_output)
    weather_result["returncode"] = returncode
    weather_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
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

    stdout_clean = strip_ansi(stdout)
    stderr_clean = strip_ansi(stderr)
    combined_output = stdout_clean
    if stderr_clean.strip():
        print(f"[WARN] stderr: {stderr_clean[:500]}")
        combined_output += "\n" + stderr_clean

    list_set_result = validate_list_set_output(combined_output)
    list_set_result["returncode"] = returncode
    list_set_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
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
