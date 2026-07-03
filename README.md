# AiAgent-test

基于 OpenCode CLI 的本地模型服务自动化校验脚本集合，用于评估 LLM 在工具调用、知识问答、多轮对话、结构化输出、翻译等场景下的能力。

## 项目结构

```
AiAgent-test/
├── scripts/
│   └── validate_opencode.py   # 主校验脚本（包含 8 个测试用例）
├── config/
│   ├── opencode.json          # 运行时使用的配置文件
│   └── opencode_template.json # 配置模板（Jenkins 动态渲染）
├── Dockerfile                 # 运行镜像构建
├── Jenkinsfile                # CI 流水线
├── requirements.txt           # 仅依赖 Python 标准库
└── README.md
```

## 环境要求

- Python 3.8+
- 已安装 `opencode` CLI（[opencode.ai](https://opencode.ai)）
- 可访问的 LLM API 服务（OpenAI 兼容协议）

依赖说明：本项目仅使用 Python 标准库，无需 `pip install`。

## 快速开始

### 1. 配置环境变量

```bash
# Linux / macOS
export BASE_URL="http://your-llm-service:8000"
export API_KEY="your-api-key"

# Windows PowerShell
$env:BASE_URL = "http://your-llm-service:8000"
$env:API_KEY  = "your-api-key"
```

### 2. 运行校验脚本

```bash
python scripts/validate_opencode.py \
  --model custom-openai/kimi-k2.5 \
  --config-path ./config/opencode.json \
  --work-dir . \
  --base-url "$BASE_URL" \
  --engine vllm \
  --chip nvidia-h100 \
  --pd disaggregated \
  --tester zhangsan \
  --build-number 1
```

### 3. 查看结果

执行完成后，报告与原始输出位于 `./results/<tester>/<build>/<chip>/<model>/<timestamp>/`：

```
results/
└── <tester>/<build>/<chip>/<model>/<YYYYMMDDHHMMSS>/
    ├── validation_results.json   # 结构化校验结果
    ├── validation_report.md      # Markdown 报告
    ├── validation_report.html    # HTML 报告（可直接邮件发送）
    ├── smoke_output.txt          # 各用例原始输出
    ├── weather_output.txt
    ├── list_set_output.txt
    ├── multi_turn_output.txt
    ├── ai_news_output.txt
    ├── boiling_point_output.txt
    ├── sales_table_output.txt
    ├── translation_output.txt
    ├── json_object_output.txt
    └── math_output.txt
```

## 脚本参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--model` | ✅ | — | 模型名，格式 `provider/model`，例如 `custom-openai/kimi-k2.5` |
| `--config-path` | ✅ | — | opencode 配置文件路径 |
| `--work-dir` | ✅ | — | opencode 执行的工作目录 |
| `--timeout` | ❌ | `300` | 单个用例超时时间（秒） |
| `--output-dir` | ❌ | `./results` | 结果输出根目录 |
| `--base-url` | ❌ | — | LLM API Base URL（同时会做连通性预检） |
| `--engine` | ❌ | — | 推理框架标签，写入报告 |
| `--chip` | ❌ | — | 芯片平台标签，写入报告 |
| `--pd` | ❌ | — | Prefill/Decode 分离模式标签，写入报告 |
| `--tester` | ❌ | — | 测试人员名，参与结果目录命名 |
| `--build-number` | ❌ | `0` | Jenkins 构建号，参与结果目录命名 |
| `--curdate` | ❌ | 当前时间 | 结果目录时间戳（`YYYYMMDDHHMMSS`） |

## 测试用例一览

| # | 名称 | 类型 | 校验要点 |
|---|------|------|----------|
| 0 | Smoke Test | 冒烟 | opencode run 基本可用 |
| 1 | Beijing Weather | 工具调用 | 是否调用工具获取实时天气 + 北京/温度/时间信息 |
| 2 | List vs Set in Python | 知识问答 | 中英文关键术语 + 无乱码/无重复 |
| 3 | Multi-turn Dialogue | 多轮对话 | 上下文记忆 + 求和 `178` + 质数识别 |
| 4 | AI Computing News | 工具调用 | 智算相关关键词 + 搜索工具使用 + 新闻结构 |
| 5 | Boiling Point of Water | 知识问答 | `100°C` 正确答案 + 温度/沸点关键词 |
| 6 | Sales Data Table | 结构化输出 | 表格结构 + 月份/销售/汇总列 |
| 7 | Chinese↔English Translation | 翻译 | 中→英、英→中双向 + 关键术语命中 |
| 8 | JSON Object | 结构化输出 | 解析出 JSON 对象 + name/age/city 字段齐全且类型正确 |
| 9 | Math Problem Solving | 数学推理 | 1+1=2 + 二元一次方程组解 x=3,y=2 + 求解过程关键词 |

## 通过 / 失败判定

- 所有用例的 `validate_*` 函数返回 `passed=True` 时整体 PASSED；
- 任一用例失败，进程退出码为 `1`，CI 流水线可据此判定红/绿。

## 通过 Jenkins 运行

仓库已附带 `Jenkinsfile`，典型流水线步骤：

1. 构建镜像：`docker build -t opencode-validator .`
2. 在容器内以模板 `config/opencode_template.json` 动态渲染 `opencode.json`（替换 `MODEL`、`BASE_URL`、`API_KEY`）
3. 执行 `python scripts/validate_opencode.py ...`
4. 归档 `results/` 目录、发送 HTML 邮件报告

## 常见问题

**Q: 运行报错 `opencode: command not found`？**
A: 请先安装 opencode CLI，并确保其在 `PATH` 中。

**Q: 提示 `Environment variable BASE_URL is not set`？**
A: `config/opencode.json` 中 `{env:BASE_URL}` 占位符需要在执行前导出环境变量。

**Q: 想新增测试用例？**
A: 在 `scripts/validate_opencode.py` 中仿照现有模式：实现 `validate_xxx_output()` + 在 `main()` 中追加 `Test N` 块。

## License

参见 `LICENSE`。
