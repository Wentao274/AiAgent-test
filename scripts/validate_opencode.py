#!/usr/bin/env python3
"""OpenCode CLI Validation Script

Validates:
1. Tool calling: Get Beijing current weather
2. Knowledge: List vs Set differences in Python (no garbled/nonsense text)
3. Multi-turn dialogue / context memory
4. Tool calling: AI computing news search
5. Knowledge: Boiling point of water
6. Structured output: sales data monthly table template
7. Translation: Chinese <-> English mutual translation
8. Structured output: JSON object with name/age/city fields
9. Math problem solving: arithmetic (1+1) and binary linear system
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


def _snapshot_files(directory):
    """Take a snapshot of all files in a directory (recursive)."""
    files = set()
    for root, dirs, filenames in os.walk(directory):
        for name in filenames:
            files.add(os.path.join(root, name))
        for name in dirs:
            pass
    return files


def _cleanup_new_files(directory, snapshot_before, protected_dirs=None):
    """Remove files created after the snapshot, excluding protected dirs."""
    if protected_dirs is None:
        protected_dirs = set()

    snapshot_after = _snapshot_files(directory)
    new_files = snapshot_after - snapshot_before

    removed = []
    for fpath in sorted(new_files):
        skip = False
        for pd in protected_dirs:
            if fpath.startswith(pd):
                skip = True
                break
        if skip:
            continue
        try:
            os.remove(fpath)
            removed.append(fpath)
        except Exception:
            pass

    for root, dirs, filenames in os.walk(directory, topdown=False):
        for d in dirs:
            dpath = os.path.join(root, d)
            skip = False
            for pd in protected_dirs:
                if dpath.startswith(pd) or pd.startswith(dpath):
                    skip = True
                    break
            if skip:
                continue
            try:
                if not os.listdir(dpath):
                    os.rmdir(dpath)
                    removed.append(dpath + "/")
            except Exception:
                pass

    if removed:
        print(f"[INFO] Cleaned up {len(removed)} file(s) created by model: {removed}")
    return removed


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

    results_dir = os.path.join(work_dir, "results")
    snapshot_before = _snapshot_files(work_dir)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
            env=env,
        )
        _cleanup_new_files(work_dir, snapshot_before, protected_dirs={results_dir})
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

    time_pattern = re.compile(
        r"\d{1,2}[:：]\d{2}[:：]?\d{0,2}"
        r"|\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?"
        r"|北京时间|UTC|CST|GMT"
    )
    has_time = bool(time_pattern.search(output))
    details["has_time_info"] = has_time
    if not has_time:
        issues.append(
            "Output does not contain time information (expected Beijing time)"
        )

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
        "output_preview": output[:3000] if output else "",
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
        "output_preview": output[:3000] if output else "",
    }


def validate_multi_turn_output(output):
    """Validate multi-turn dialogue output.

    Prompt asks the model to remember numbers, compute sum, identify primes.
    Checks:
    - Model correctly references prior context (the numbers 7, 13, 29, 129)
    - Provides correct sum (178)
    - Identifies prime numbers correctly
    - Output is coherent across turns
    """
    issues = []
    details = {}

    context_keywords = ["7", "13", "29", "129"]
    found_numbers = [n for n in context_keywords if n in output]
    details["referenced_numbers"] = found_numbers
    if len(found_numbers) < 2:
        issues.append(
            f"Model did not reference enough prior context numbers (found {len(found_numbers)}: {found_numbers})"
        )

    has_correct_sum = "178" in output
    details["correct_sum_178"] = has_correct_sum
    if not has_correct_sum:
        issues.append("Model did not provide correct sum (178) of 7+13+29+129")

    prime_keywords = ["质数", "素数", "prime"]
    has_prime_mention = any(kw in output for kw in prime_keywords)
    details["mentions_prime"] = has_prime_mention
    if not has_prime_mention:
        issues.append("Model did not mention prime numbers (质数/素数/prime)")

    turn_indicators = [
        "第",
        "步骤",
        "轮",
        "Step",
        "step",
        "1.",
        "2.",
        "3.",
        "一",
        "二",
        "三",
    ]
    found_turn_indicators = [kw for kw in turn_indicators if kw in output]
    details["turn_indicators"] = found_turn_indicators
    if not found_turn_indicators:
        issues.append("Output lacks multi-turn structure indicators")

    if len(output.strip()) < 50:
        issues.append("Output is too short, possibly incomplete")

    garbled_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    garbled_matches = garbled_pattern.findall(output)
    details["garbled_chars_count"] = len(garbled_matches)
    if garbled_matches:
        issues.append(
            f"Output contains {len(garbled_matches)} garbled/control characters"
        )

    return {
        "test_name": "Multi-turn Dialogue - Context Memory",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def validate_ai_computing_news_output(output):
    """Validate AI computing news query output.

    Checks:
    - Output contains AI computing / intelligent computing keywords
    - Tool usage indicators present (webfetch/websearch)
    - Output mentions specific news/events (not generic description)
    - No garbled text
    """
    issues = []
    details = {}

    ai_computing_keywords = [
        "智算",
        "算力",
        "AI算力",
        "智能计算",
        "算力中心",
        "智算中心",
        "GPU",
        "芯片",
        "大模型",
        "超算",
        "数据中心",
        "computing",
        "AI infrastructure",
        "data center",
        "算力网络",
        "算力集群",
        "国产算力",
        "异构算力",
    ]
    found_kws = [kw for kw in ai_computing_keywords if kw in output]
    details["found_ai_computing_keywords"] = found_kws

    if len(found_kws) < 2:
        issues.append(
            f"Output lacks AI computing keywords (found {len(found_kws)}: {found_kws})"
        )

    tool_indicators = [
        "webfetch",
        "websearch",
        "WebSearch",
        "WebFetch",
        "搜索",
        "查询",
        "检索",
        "查找",
        "http",
        "news",
        "news.qq.com",
        "36kr",
        "jiqizhixin",
    ]
    found_tool_indicators = [
        kw for kw in tool_indicators if kw.lower() in output.lower()
    ]
    details["tool_indicators"] = found_tool_indicators
    if not found_tool_indicators:
        issues.append("No tool usage indicators found (model may not have used tools)")

    news_structure_indicators = [
        "新闻",
        "动态",
        "消息",
        "报道",
        "资讯",
        "公告",
        "1.",
        "2.",
        "3.",
        "一、",
        "二、",
        "三、",
        "近日",
        "近期",
        "今年",
        "最新",
    ]
    found_news_indicators = [kw for kw in news_structure_indicators if kw in output]
    details["news_structure_indicators"] = found_news_indicators
    if not found_news_indicators:
        issues.append("Output lacks news/announcement structure indicators")

    if len(output.strip()) < 100:
        issues.append("Output is too short for a news query response")

    garbled_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    garbled_matches = garbled_pattern.findall(output)
    details["garbled_chars_count"] = len(garbled_matches)
    if garbled_matches:
        issues.append(
            f"Output contains {len(garbled_matches)} garbled/control characters"
        )

    return {
        "test_name": "Tool Calling - AI Computing News",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def validate_boiling_point_output(output):
    """Validate boiling point of water knowledge output.

    Checks:
    - Output contains correct boiling point (100°C or 100 degrees Celsius)
    - Contains temperature-related keywords
    - No garbled text
    - Output is coherent
    """
    issues = []
    details = {}

    # Accept "100" with an explicit temperature unit, "一百度", or a standalone
    # "100" token. The prompt already specifies Celsius ("多少摄氏度"), so a
    # terse bare "100" is an unambiguous and correct answer. To avoid false
    # positives where "100" appears in unrelated context (e.g. "海拔100米处
    # 沸点为90度"), do NOT accept a stray 100 when the model has explicitly
    # stated a *different* temperature (a number + temp unit that isn't 100).
    temp_unit_re = r"(?:°|℃|度|摄氏度|华氏度|摄氏)"
    stated_temps = re.findall(r"(\d+(?:\.\d+)?)\s*" + temp_unit_re, output)
    explicit_wrong_temp = any(abs(float(n) - 100) > 1e-9 for n in stated_temps)
    has_100_token = bool(re.search(r"(?<![\d.])100(?![\d.])", output))
    has_correct_answer = (
        bool(re.search(r"100\s*" + temp_unit_re, output))
        or "一百度" in output
        or (has_100_token and not explicit_wrong_temp)
    )
    details["correct_boiling_point"] = has_correct_answer
    if not has_correct_answer:
        issues.append("Output does not contain correct boiling point of water (100°C)")

    temp_keywords = [
        "沸点",
        "沸腾",
        "摄氏",
        "°C",
        "℃",
        "度",
        "boiling",
        "Celsius",
        "100",
    ]
    found_kws = [kw for kw in temp_keywords if kw in output]
    details["found_temperature_keywords"] = found_kws
    # Require >=2 temperature keywords, unless the correct numeric answer is
    # already present (the number itself makes the output temperature-relevant).
    if len(found_kws) < 2 and not has_correct_answer:
        issues.append(
            f"Output lacks temperature-related keywords (found {len(found_kws)}: {found_kws})"
        )

    context_keywords = [
        "水",
        "标准大气压",
        "压强",
        "海拔",
        "water",
        "atmosphere",
        "pressure",
    ]
    found_context = [kw for kw in context_keywords if kw in output]
    details["found_context_keywords"] = found_context

    # A terse but correct answer (e.g. bare "100") is legitimately short; only
    # flag shortness when the answer is not already correct.
    if len(output.strip()) < 10 and not has_correct_answer:
        issues.append("Output is too short, possibly incomplete")

    garbled_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    garbled_matches = garbled_pattern.findall(output)
    details["garbled_chars_count"] = len(garbled_matches)
    if garbled_matches:
        issues.append(
            f"Output contains {len(garbled_matches)} garbled/control characters"
        )

    return {
        "test_name": "Knowledge - Boiling Point of Water",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def validate_sales_table_output(output):
    """Validate sales data monthly table template output.

    Checks:
    - Output contains table structure (borders, pipes, or markdown table)
    - Contains month-related keywords
    - Contains sales-related keywords
    - No garbled text
    """
    issues = []
    details = {}

    table_indicators = [
        "|",
        "---",
        "+",
        "-",
        "┌",
        "┬",
        "┐",
        "│",
        "├",
        "┼",
        "┤",
        "└",
        "┴",
        "┘",
    ]
    found_table = [kw for kw in table_indicators if kw in output]
    details["table_structure_indicators"] = found_table
    if len(found_table) < 2:
        issues.append(
            f"Output lacks table structure indicators (found {len(found_table)}: {found_table})"
        )

    month_keywords = [
        "月份",
        "月",
        "1月",
        "2月",
        "January",
        "February",
        "Jan",
        "Feb",
        "Q1",
        "Q2",
        "月度",
        "季度",
    ]
    found_months = [kw for kw in month_keywords if kw in output]
    details["found_month_keywords"] = found_months
    if not found_months:
        issues.append("Output does not contain month-related keywords")

    sales_keywords = [
        "销售",
        "销售额",
        "销量",
        "营收",
        "收入",
        "利润",
        "sales",
        "revenue",
        "profit",
        "amount",
        "金额",
        "数量",
    ]
    found_sales = [kw for kw in sales_keywords if kw in output]
    details["found_sales_keywords"] = found_sales
    if not found_sales:
        issues.append("Output does not contain sales-related keywords")

    column_keywords = [
        "合计",
        "总计",
        "总计/平均",
        "同比",
        "环比",
        "增长率",
        "Total",
        "Sum",
        "YoY",
    ]
    found_columns = [kw for kw in column_keywords if kw in output]
    details["found_column_keywords"] = found_columns

    if len(output.strip()) < 50:
        issues.append("Output is too short for a table template response")

    garbled_pattern = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    garbled_matches = garbled_pattern.findall(output)
    details["garbled_chars_count"] = len(garbled_matches)
    if garbled_matches:
        issues.append(
            f"Output contains {len(garbled_matches)} garbled/control characters"
        )

    return {
        "test_name": "Structured Output - Sales Data Table Template",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def validate_translation_output(output):
    """Validate Chinese-English mutual translation output.

    Prompt asks the model to:
    1. Translate a Chinese sentence to English
    2. Translate an English sentence to Chinese

    Checks:
    - Contains key English words from the Chinese->English translation
      ("人工智能"->"artificial intelligence", "改变/改变着"->"changing",
       "生活"->"life/lives/lifestyle")
    - Contains Chinese translation of the English sentence
      ("Knowledge is power." -> "知识就是力量" / "知识就是力量。")
    - Contains translation structure indicators (中文/英文/English/翻译/translation)
    - No garbled text
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

    en_keywords = [
        "artificial intelligence",
        "AI",
        "changing",
        "change",
        "transform",
        "lifestyle",
        "way of life",
        "our lives",
        "way we live",
        "we live",
        "live",
        "life",
    ]
    found_en = [kw for kw in en_keywords if kw.lower() in output.lower()]
    details["found_en_translation_keywords"] = found_en
    if len(found_en) < 2:
        issues.append(
            f"Chinese->English translation lacks expected English keywords "
            f"(found {len(found_en)}: {found_en})"
        )

    zh_keywords = [
        "知识",
        "力量",
        "知识就是力量",
    ]
    found_zh = [kw for kw in zh_keywords if kw in output]
    details["found_zh_translation_keywords"] = found_zh
    if len(found_zh) < 2:
        issues.append(
            f"English->Chinese translation lacks expected Chinese keywords "
            f"(found {len(found_zh)}: {found_zh})"
        )

    structure_indicators = [
        "翻译",
        "译文",
        "中文",
        "英文",
        "中译英",
        "英译中",
        "任务一",
        "任务二",
        "Chinese",
        "English",
        "translation",
        "translate",
        "Task 1",
        "Task 2",
        "译",
    ]
    found_struct = [kw for kw in structure_indicators if kw in output]
    details["translation_structure_indicators"] = found_struct
    if len(found_struct) < 2:
        issues.append(
            f"Output lacks translation structure indicators (found "
            f"{len(found_struct)}: {found_struct})"
        )

    output_lower = output.lower()
    # Concept-based gate: ZH->EN must cover (AI) + (change) + (life/way-of-living);
    # EN->ZH must cover (knowledge) + (power).
    has_en_ai = (
        "artificial intelligence" in output_lower
        or "ai" in output_lower.split()
        or "AI" in output.split()
    )
    has_en_change = any(
        k in output_lower for k in ["changing", "change", "transform", "shap"]
    )
    has_en_life = any(
        k in output_lower
        for k in [
            "life",
            "lifestyle",
            "live",
            "way of life",
            "way we live",
            "our lives",
        ]
    )
    has_zh_knowledge = "知识" in output
    has_zh_power = "力量" in output
    both_tasks_present = (
        has_en_ai
        and has_en_change
        and has_en_life
        and has_zh_knowledge
        and has_zh_power
    )
    details["both_translations_present"] = both_tasks_present
    if not both_tasks_present:
        issues.append(
            "Output does not contain expected translations for both directions "
            "(missing ZH->EN keywords or EN->ZH keywords)"
        )

    if len(output.strip()) < 50:
        issues.append("Output is too short, possibly incomplete")

    words = output.split()
    if len(words) > 10:
        unique_ratio = len(set(words)) / len(words)
        details["unique_word_ratio"] = round(unique_ratio, 3)
        if unique_ratio < 0.3:
            issues.append(
                f"Output has excessive repetition (unique ratio: "
                f"{unique_ratio:.2f}), possibly nonsensical"
            )

    return {
        "test_name": "Translation - Chinese<->English Mutual",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def validate_json_object_output(output):
    """Validate structured JSON object output.

    Prompt asks the model to return a JSON object containing name, age, and city.

    Checks:
    - Output contains a parseable JSON object (extracted from code fences or raw)
    - JSON object has the three required fields (accept both English and Chinese keys)
    - Field types are correct: name/姓名 is str, age/年龄 is number,
      city/城市 is str
    - No garbled text
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

    json_obj = None
    extraction_error = None

    fence_pattern = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.DOTALL)
    fence_matches = fence_pattern.findall(output)
    for candidate in fence_matches:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                json_obj = parsed
                break
        except json.JSONDecodeError:
            continue

    if json_obj is None:
        brace_pattern = re.compile(r"\{[^{}]*\}", re.DOTALL)
        for candidate in brace_pattern.findall(output):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    json_obj = parsed
                    break
            except json.JSONDecodeError:
                continue

    if json_obj is None:
        try:
            parsed = json.loads(output.strip())
            if isinstance(parsed, dict):
                json_obj = parsed
        except json.JSONDecodeError as e:
            extraction_error = str(e)

    if json_obj is None:
        issues.append(
            f"Output does not contain a parseable JSON object"
            + (f" (extraction error: {extraction_error})" if extraction_error else "")
        )
        details["json_parsed"] = False
        details["json_object"] = None
        if len(output.strip()) < 10:
            issues.append("Output is too short, possibly incomplete")
        return {
            "test_name": "Structured Output - JSON Object",
            "passed": len(issues) == 0,
            "issues": issues,
            "details": details,
            "output_preview": output[:3000] if output else "",
        }

    details["json_parsed"] = True
    details["json_object"] = json_obj
    details["json_keys"] = list(json_obj.keys())

    name_keys = ["name", "姓名"]
    age_keys = ["age", "年龄"]
    city_keys = ["city", "城市"]

    def _find_value(keys):
        for k in keys:
            if k in json_obj:
                return k, json_obj[k]
        return None, None

    name_key, name_val = _find_value(name_keys)
    age_key, age_val = _find_value(age_keys)
    city_key, city_val = _find_value(city_keys)

    details["name_field"] = f"{name_key}={name_val!r}" if name_key else "missing"
    details["age_field"] = f"{age_key}={age_val!r}" if age_key else "missing"
    details["city_field"] = f"{city_key}={city_val!r}" if city_key else "missing"

    if name_key is None:
        issues.append("JSON object is missing the name field (name/姓名)")
    elif not isinstance(name_val, str) or not name_val.strip():
        issues.append(
            f"JSON name field ({name_key}) should be a non-empty string, "
            f"got {type(name_val).__name__}: {name_val!r}"
        )

    if age_key is None:
        issues.append("JSON object is missing the age field (age/年龄)")
    elif isinstance(age_val, bool) or not isinstance(age_val, (int, float)):
        issues.append(
            f"JSON age field ({age_key}) should be a number, "
            f"got {type(age_val).__name__}: {age_val!r}"
        )
    elif isinstance(age_val, (int, float)) and (age_val < 0 or age_val > 150):
        issues.append(
            f"JSON age field ({age_key}) value {age_val} is out of plausible range"
        )

    if city_key is None:
        issues.append("JSON object is missing the city field (city/城市)")
    elif not isinstance(city_val, str) or not city_val.strip():
        issues.append(
            f"JSON city field ({city_key}) should be a non-empty string, "
            f"got {type(city_val).__name__}: {city_val!r}"
        )

    return {
        "test_name": "Structured Output - JSON Object",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def validate_math_output(output):
    """Validate math problem solving output.

    Prompt asks the model to solve two problems:
    1. Simple arithmetic: 1 + 1 = ?
    2. A system of two linear equations in two unknowns:
       2x + 3y = 12
       x - y = 1
       (correct solution: x = 3, y = 2)

    Checks:
    - First answer contains the correct result "2"
    - Second answer contains the correct solution x=3, y=2
    - Contains math-related keywords
    - Output is structured with step indicators
    - No garbled text
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

    # Normalize away markdown emphasis/strong, code spans, and common LaTeX
    # inline delimiters so the answer digit sits directly next to its lead-in
    # (e.g. "1 + 1 = **2**" -> "1 + 1 = 2", "$\boxed{2}$" -> "2").
    norm_output = re.sub(r"\\boxed\{|\\text\{|\\mathrm\{|\\mathbf\{", "", output)
    norm_output = re.sub(r"[*_`~$\\(){}\[\]]", "", norm_output)
    first_answer_patterns = [
        # 1 + 1 = 2 (ASCII or full-width operators)
        r"1\s*[+\uFF0B]\s*1\s*[=\uFF1D]\s*2",
        # 1 加 1 等于/=/＝/得/为/是 2
        r"1\s*加\s*1\s*(?:等于|[=\uFF1D]|得|为|是)\s*2",
        # 等于 / 答案是 / 结果(为|是) [:：]? 2
        r"等于\s*[:：]?\s*2",
        r"(?:最终)?答案(?:是为?|为|是|等于)?\s*[:：]?\s*2",
        r"结果(?:为|是|等于)\s*[:：]?\s*2",
        # 1 + 1 得/为/是 2
        r"1\s*[+\uFF0B]\s*1\s*(?:得|为|是)\s*2",
    ]
    has_answer_2 = any(
        re.search(p, text)
        for text in (output, norm_output)
        for p in first_answer_patterns
    )
    details["first_answer_correct_2"] = has_answer_2
    if not has_answer_2:
        issues.append("First question (1+1) answer does not contain correct result (2)")

    x_solution_patterns = [
        r"x\s*=\s*3\b",
        r"x\s*的值?\s*(?:为|是|等于)\s*3\b",
        r"x\s*[:：]\s*3\b",
        r"未知数.*?3",
    ]
    has_x_3 = any(re.search(p, output) for p in x_solution_patterns)
    details["has_x_equals_3"] = has_x_3
    if not has_x_3:
        issues.append("System solution does not contain x = 3")

    y_solution_patterns = [
        r"y\s*=\s*2\b",
        r"y\s*的值?\s*(?:为|是|等于)\s*2\b",
        r"y\s*[:：]\s*2\b",
    ]
    has_y_2 = any(re.search(p, output) for p in y_solution_patterns)
    details["has_y_equals_2"] = has_y_2
    if not has_y_2:
        issues.append("System solution does not contain y = 2")

    math_keywords = [
        "方程",
        "方程组",
        "解",
        "代入",
        "消元",
        "加减",
        "求解",
        "计算",
        "等式",
        "未知数",
        "答案",
        "得",
        "等于",
        "solution",
        "equation",
        "substitut",
        "eliminat",
        "solve",
    ]
    found_math = [kw for kw in math_keywords if kw.lower() in output.lower()]
    details["found_math_keywords"] = found_math

    import re

    has_math_expr = bool(re.search(r"\d\s*[+\-*/=]\s*\d", output))
    details["has_math_expression"] = has_math_expr

    if len(found_math) < 2 and not has_math_expr:
        issues.append(
            f"Output lacks math-related keywords (found {len(found_math)}: {found_math})"
        )

    step_indicators = [
        "第一",
        "第二",
        "1.",
        "2.",
        "①",
        "②",
        "Step",
        "step",
        "题一",
        "题二",
        "问题一",
        "问题二",
        "Problem 1",
        "Problem 2",
        "Question 1",
        "Question 2",
    ]
    found_steps = [kw for kw in step_indicators if kw in output]
    details["step_indicators"] = found_steps
    if len(found_steps) < 2:
        issues.append(
            f"Output lacks step/problem structure indicators (found "
            f"{len(found_steps)}: {found_steps})"
        )

    if len(output.strip()) < 50:
        issues.append("Output is too short, possibly incomplete")

    return {
        "test_name": "Math Problem Solving - Arithmetic & Linear System",
        "passed": len(issues) == 0,
        "issues": issues,
        "details": details,
        "output_preview": output[:3000] if output else "",
    }


def generate_markdown_report(results, output_dir, params):
    """Generate markdown report."""
    summary = results["summary"]
    status_icon = "PASSED" if summary["failed"] == 0 else "FAILED"

    report = f"""# OpenCode CLI Validation Report

**Timestamp:** {results["timestamp"]}
**Model:** {results["model"]}
**Base URL:** {params.get("base_url", "N/A")}
**Engine:** {params.get("engine", "N/A")}
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
        if test.get("prompt"):
            report += f"**Prompt:** {test['prompt']}\n\n"
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


def generate_html_report(results, output_dir, params):
    """Generate HTML report for email embedding."""
    summary = results["summary"]
    status_icon = "PASSED" if summary["failed"] == 0 else "FAILED"
    status_color = "#4CAF50" if summary["failed"] == 0 else "#f44336"

    html = '<div style="font-family:Arial,sans-serif;">\n'

    html += "<h2>OpenCode CLI Validation Report</h2>\n"
    html += f"<p><strong>Timestamp:</strong> {results['timestamp']}<br/>\n"
    html += f"<strong>Model:</strong> {results['model']}<br/>\n"
    html += f"<strong>Base URL:</strong> {params.get('base_url', 'N/A')}<br/>\n"
    html += f"<strong>Engine:</strong> {params.get('engine', 'N/A')}<br/>\n"
    html += f"<strong>Chip:</strong> {params.get('chip', 'N/A')}<br/>\n"
    html += f"<strong>PD Mode:</strong> {params.get('pd', 'N/A')}<br/>\n"
    html += f'<strong>Overall Status:</strong> <span style="color:{status_color};font-weight:bold;">{status_icon}</span></p>\n'

    html += "<h2>Summary</h2>\n"
    html += '<table style="border-collapse:collapse;width:50%;">\n'
    html += '<tr style="background:#f2f2f2;"><th style="border:1px solid #ddd;padding:8px;text-align:left;">Metric</th><th style="border:1px solid #ddd;padding:8px;text-align:left;">Value</th></tr>\n'
    html += f'<tr><td style="border:1px solid #ddd;padding:8px;">Total Tests</td><td style="border:1px solid #ddd;padding:8px;">{summary["total"]}</td></tr>\n'
    html += f'<tr><td style="border:1px solid #ddd;padding:8px;">Passed</td><td style="border:1px solid #ddd;padding:8px;">{summary["passed"]}</td></tr>\n'
    html += f'<tr><td style="border:1px solid #ddd;padding:8px;">Failed</td><td style="border:1px solid #ddd;padding:8px;">{summary["failed"]}</td></tr>\n'
    html += f'<tr><td style="border:1px solid #ddd;padding:8px;">Pass Rate</td><td style="border:1px solid #ddd;padding:8px;">{summary["pass_rate"]}</td></tr>\n'
    html += "</table>\n"

    html += "<h2>Test Details</h2>\n"
    for test in results["tests"]:
        status = "PASSED" if test["passed"] else "FAILED"
        color = "#4CAF50" if test["passed"] else "#f44336"
        html += f'<div style="margin-bottom:20px;border:1px solid #ddd;padding:15px;background:#fafafa;border-radius:5px;">\n'
        html += f'<h3 style="margin-top:0;color:{color};">{test["test_name"]} - {status}</h3>\n'

        if test.get("prompt"):
            safe_prompt = (
                test["prompt"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br/>")
            )
            html += f"<p><strong>Prompt:</strong> {safe_prompt}</p>\n"

        if test.get("issues"):
            html += "<p><strong>Issues:</strong></p><ul>\n"
            for issue in test["issues"]:
                safe_issue = (
                    issue.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                html += f"<li>{safe_issue}</li>\n"
            html += "</ul>\n"

        if test.get("details"):
            html += '<p><strong>Validation Details:</strong></p><table style="border-collapse:collapse;width:100%;">\n'
            html += '<tr style="background:#f2f2f2;"><th style="border:1px solid #ddd;padding:6px;text-align:left;">Key</th><th style="border:1px solid #ddd;padding:6px;text-align:left;">Value</th></tr>\n'
            for key, value in test["details"].items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value) if value else "none"
                safe_value = (
                    str(value)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                safe_key = (
                    key.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                html += f'<tr><td style="border:1px solid #ddd;padding:6px;">{safe_key}</td><td style="border:1px solid #ddd;padding:6px;">{safe_value}</td></tr>\n'
            html += "</table>\n"

        safe_preview = (
            test.get("output_preview", "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html += "<p><strong>Output Preview:</strong></p>\n"
        html += f'<pre style="background:#f4f4f4;border:1px solid #ddd;border-radius:4px;padding:12px;overflow-x:auto;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-all;">{safe_preview}</pre>\n'
        html += "</div>\n<hr/>\n"

    html += "</div>\n"

    html_file = os.path.join(output_dir, "validation_report.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] HTML report saved to: {html_file}")
    return html_file


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
        help="Base output directory for results",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Base URL of LLM API",
    )
    parser.add_argument("--engine", default="", help="Inference framework (for report)")
    parser.add_argument("--chip", default="", help="Chip platform (for report)")
    parser.add_argument("--pd", default="", help="PD mode (for report)")
    parser.add_argument("--tester", default="", help="Tester name (for report)")
    parser.add_argument("--build-number", default="0", help="Jenkins build number")
    parser.add_argument(
        "--curdate", default="", help="Timestamp for output directory (YYYYMMDDHHmmss)"
    )
    args = parser.parse_args()

    model_name = args.model.split("/")[-1]
    curdate = args.curdate if args.curdate else datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = os.path.join(
        args.output_dir,
        args.tester,
        args.build_number,
        args.chip,
        model_name,
        curdate,
    )
    os.makedirs(output_dir, exist_ok=True)
    print(f"[INFO] Output directory: {output_dir}")

    params = {
        "base_url": args.base_url,
        "engine": args.engine,
        "chip": args.chip,
        "pd": args.pd,
        "tester": args.tester,
    }

    results = {
        "timestamp": datetime.now().isoformat(),
        "model": args.model,
        "output_dir": output_dir,
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
            os.path.join(output_dir, "validation_results.json"), "w", encoding="utf-8"
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
        timeout=600,
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
                "prompt": smoke_prompt,
                "passed": False,
                "issues": [
                    f"opencode run returned code {returncode}, stdout too short or empty"
                ],
                "details": {
                    "returncode": returncode,
                    "stdout_preview": stdout_clean[:500],
                    "stderr_preview": stderr_clean[:500],
                },
                "output_preview": stdout_clean[:3000],
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
            os.path.join(output_dir, "validation_results.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        with open(
            os.path.join(output_dir, "smoke_output.txt"), "w", encoding="utf-8"
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

    weather_prompt = "请按北京时间输出当前时间，并获取北京市当前的天气情况，告诉我现在的温度和天气状况。请使用工具来获取实时天气信息。"
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
    weather_result["prompt"] = weather_prompt

    status = "PASSED" if weather_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if weather_result["issues"]:
        for issue in weather_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "weather_output.txt"), "w", encoding="utf-8"
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
    list_set_result["prompt"] = list_set_prompt

    status = "PASSED" if list_set_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if list_set_result["issues"]:
        for issue in list_set_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "list_set_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 3: Multi-turn Dialogue - Context Memory
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 3: Multi-turn Dialogue - Context Memory")
    print("=" * 60)

    multi_turn_prompt = (
        "我们来玩一个数字记忆游戏，请按步骤回答：\n"
        "第一步：请记住这四个数字：7、13、29、129。\n"
        "第二步：请计算这四个数字的和是多少？\n"
        "第三步：这四个数字中哪些是质数？\n"
        "请依次回答每一步。"
    )
    stdout, stderr, returncode = run_opencode(
        multi_turn_prompt,
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

    multi_turn_result = validate_multi_turn_output(combined_output)
    multi_turn_result["returncode"] = returncode
    multi_turn_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(multi_turn_result)
    multi_turn_result["prompt"] = multi_turn_prompt

    status = "PASSED" if multi_turn_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if multi_turn_result["issues"]:
        for issue in multi_turn_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "multi_turn_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 4: Tool Calling - AI Computing News
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 4: Tool Calling - AI Computing News")
    print("=" * 60)

    ai_news_prompt = "请搜索并告诉我最近关于智算中心、算力方面的新闻或动态，至少列出2-3条相关资讯。请使用搜索工具获取最新信息。"
    stdout, stderr, returncode = run_opencode(
        ai_news_prompt,
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

    ai_news_result = validate_ai_computing_news_output(combined_output)
    ai_news_result["returncode"] = returncode
    ai_news_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(ai_news_result)
    ai_news_result["prompt"] = ai_news_prompt

    status = "PASSED" if ai_news_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if ai_news_result["issues"]:
        for issue in ai_news_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "ai_news_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 5: Knowledge - Boiling Point of Water
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 5: Knowledge - Boiling Point of Water")
    print("=" * 60)

    boiling_prompt = "水的沸点是多少摄氏度？"
    stdout, stderr, returncode = run_opencode(
        boiling_prompt,
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

    boiling_result = validate_boiling_point_output(combined_output)
    boiling_result["returncode"] = returncode
    boiling_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(boiling_result)
    boiling_result["prompt"] = boiling_prompt

    status = "PASSED" if boiling_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if boiling_result["issues"]:
        for issue in boiling_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "boiling_point_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 6: Structured Output - Sales Data Table Template
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 6: Structured Output - Sales Data Table Template")
    print("=" * 60)

    sales_prompt = (
        "请编写一个临时Python脚本 scripts/sales_table_template.py，"
        "该脚本的功能是打印一个销售数据按月份统计的表格模版到控制台。"
        "表格须包含以下列：月份、销售额、同比、环比、合计，"
        "并给出1月到12月的示例行以及最后一行的合计行。"
        "请使用Markdown表格语法输出。"
        "编写完成后请立即运行该脚本（python scripts/sales_table_template.py），"
        "使表格内容输出到控制台。"
    )
    stdout, stderr, returncode = run_opencode(
        sales_prompt,
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

    sales_result = validate_sales_table_output(combined_output)
    sales_result["returncode"] = returncode
    sales_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(sales_result)
    sales_result["prompt"] = sales_prompt

    status = "PASSED" if sales_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if sales_result["issues"]:
        for issue in sales_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "sales_table_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # Clean up temp Python scripts created by the model in scripts/
    scripts_dir = os.path.join(args.work_dir, "scripts")
    if os.path.isdir(scripts_dir):
        for fname in os.listdir(scripts_dir):
            if (
                fname.endswith(".py")
                and fname != "validate_opencode.py"
                and "sales" in fname.lower()
            ):
                fpath = os.path.join(scripts_dir, fname)
                try:
                    os.remove(fpath)
                    print(f"[INFO] Cleaned up temp script: {fpath}")
                except Exception:
                    pass

    # ============================================================
    # Test 7: Translation - Chinese <-> English Mutual Translation
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 7: Translation - Chinese <-> English Mutual Translation")
    print("=" * 60)

    translation_prompt = (
        "请你完成两个翻译任务:\n"
        "任务一:请将下面这句中文翻译成英文:\n"
        "  原文:人工智能正在改变着我们的生活方式。\n"
        "任务二:请将下面这句英文翻译成中文:\n"
        "  Original: Knowledge is power.\n"
        "请分别清晰地输出两个任务的翻译结果。"
    )
    stdout, stderr, returncode = run_opencode(
        translation_prompt,
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

    translation_result = validate_translation_output(combined_output)
    translation_result["returncode"] = returncode
    translation_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(translation_result)
    translation_result["prompt"] = translation_prompt

    status = "PASSED" if translation_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if translation_result["issues"]:
        for issue in translation_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "translation_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 8: Structured Output - JSON Object
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 8: Structured Output - JSON Object")
    print("=" * 60)

    json_prompt = (
        "请返回一个包含姓名(name)、年龄(age)和城市(city)三个字段的JSON对象，"
        "只输出JSON本身，不要添加其他说明文字。"
    )
    stdout, stderr, returncode = run_opencode(
        json_prompt,
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

    json_result = validate_json_object_output(combined_output)
    json_result["returncode"] = returncode
    json_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(json_result)
    json_result["prompt"] = json_prompt

    status = "PASSED" if json_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if json_result["issues"]:
        for issue in json_result["issues"]:
            print(f"  - {issue}")

    with open(
        os.path.join(output_dir, "json_object_output.txt"), "w", encoding="utf-8"
    ) as f:
        f.write(
            f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n\n=== RETURN CODE ===\n{returncode}"
        )

    # ============================================================
    # Test 9: Math Problem Solving - Arithmetic & Linear System
    # ============================================================
    print("\n" + "=" * 60)
    print("Test 9: Math Problem Solving - Arithmetic & Linear System")
    print("=" * 60)

    math_prompt = (
        "请解答以下两道数学题：\n"
        "第一题：请问 1 + 1 等于几？\n"
        "第二题：解二元一次方程组：\n"
        "  2x + 3y = 12\n"
        "  x - y = 1\n"
        "请给出每道题的详细解答过程和最终答案。"
    )
    stdout, stderr, returncode = run_opencode(
        math_prompt,
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

    math_result = validate_math_output(combined_output)
    math_result["returncode"] = returncode
    math_result["stderr_preview"] = stderr_clean[:500] if stderr_clean else ""
    results["tests"].append(math_result)
    math_result["prompt"] = math_prompt

    status = "PASSED" if math_result["passed"] else "FAILED"
    print(f"Result: {status}")
    if math_result["issues"]:
        for issue in math_result["issues"]:
            print(f"  - {issue}")

    with open(os.path.join(output_dir, "math_output.txt"), "w", encoding="utf-8") as f:
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

    results_file = os.path.join(output_dir, "validation_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Results saved to: {results_file}")

    report_file = generate_markdown_report(results, output_dir, params)
    html_file = generate_html_report(results, output_dir, params)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
