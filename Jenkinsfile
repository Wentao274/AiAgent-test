pipeline {
    agent any
    parameters {
        string(name: 'TESTER', defaultValue: 'liwt', description: '测试人员名称')
        choice(name: 'INFRA', choices: ['vllm', 'sglang'], description: '推理框架')
        string(name: 'CHIP', defaultValue: 'nvidia-h100', description: '芯片平台名称')
        choice(name: 'PD', choices: ['agg', 'disagg'], description: 'PD分离模式,agg 表示非 PD 分离, disagg 表示 PD 分离')
        string(name: 'MODEL', defaultValue: 'kimi-k2.5', description: '模型名称（served-model-name）')
        string(name: 'MODEL_PATH', defaultValue: '/dingofs/data1/userdata/llms/moonshotai/Kimi-K2.6', description: '模型文件本地路径')
        string(name: 'BASE_URL', defaultValue: 'http://10.201.149.10:8080', description: 'API 地址，注意没有/v1后缀')
        password(name: 'API_KEY', defaultValue: 'EMPTY', description: 'API认证密钥，无需认证时保持默认EMPTY')
        text(name: 'RECIPIENTS', defaultValue: 'liwt@zetyun.com', description: '邮件接收者（逗号分隔）')
        string(name: 'WORK_DIR', defaultValue: '/dingofs/data1/userdata/liwt/maas-image/AiAgent-test', description: '测试仓库目录，请不要修改')
    }
    environment {
        SSH_CREDENTIALS = 'HOST_SSH_KEY'
        REMOTE_HOST = '10.201.132.50'
        REMOTE_USER = 'root'
        OPENCODE_IMAGE = 'my-opencode-with-python:latest'
    }

    stages {
        stage('环境检查') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    script {
                        println("=== 环境检查 ===")
                        sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
echo "=== 工作目录 ==="
cd ${params.WORK_DIR}
pwd
ls -la

echo "=== 测试参数信息 ==="
echo "测试人员: ${params.TESTER}"
echo "推理框架: ${params.INFRA}"
echo "芯片类型: ${params.CHIP}"
echo "PD分离模式: ${params.PD}"
echo "模型服务名称: ${params.MODEL}"
echo "模型路径: ${params.MODEL_PATH}"
echo "BASE_URL: ${params.BASE_URL}"
echo "BUILD_NUMBER: ${BUILD_NUMBER}"

echo "=== Docker 检查 ==="
docker --version

echo "=== 检查 opencode 镜像 ==="
docker images | grep opencode || echo "opencode 镜像未找到，将在启动时拉取"
ENDSSH
"""
                    }
                }
            }
        }

        stage('启动容器') {
            steps {
                script {
                    env.SERVED_MODEL_NAME = params.MODEL.tokenize('/')[-1]
                    def safeModel = env.SERVED_MODEL_NAME.replaceAll('\\.', '-').replaceAll('_', '-')
                    def containerName = "opencode-validate-${params.CHIP}-${safeModel}-${BUILD_NUMBER}"
                    env.CONTAINER_NAME = containerName

                    def curdate = new Date().format('yyyyMMddHHmmss')
                    env.CURDATE = curdate

                    println("=== 启动 opencode 容器 ===")
                    println("容器名: ${containerName}")
                    println("时间戳: ${curdate}")

                    sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                        sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e

echo "=== 清理旧容器 ==="
docker rm -f ${containerName} 2>/dev/null || true

echo "=== 生成 opencode.json 配置文件 ==="
cat > ${params.WORK_DIR}/config/opencode.json << 'CONFIGEOF'
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    "custom-openai": {
      "options": {
        "baseURL": "{env:BASE_URL}/v1",
        "apiKey": "{env:API_KEY}"
      },
      "models": {
        "${env.SERVED_MODEL_NAME}": {
          "name": "${env.SERVED_MODEL_NAME}"
        }
      }
    }
  },
  "model": "custom-openai/${env.SERVED_MODEL_NAME}",
  "autoupdate": false,
  "tools": {
    "webfetch": true,
    "websearch": true
  }
}
CONFIGEOF

echo "=== 配置文件内容 ==="
cat ${params.WORK_DIR}/config/opencode.json

echo "=== 启动 opencode 容器 ==="
docker run -d --name ${containerName} \
    --network host \
    --entrypoint sh \
    -v ${params.WORK_DIR}:/workspace/AiAgent-test \
    -v /etc/localtime:/etc/localtime:ro \
    -v /etc/timezone:/etc/timezone:ro \
    -e OPENCODE_CONFIG=/workspace/AiAgent-test/config/opencode.json \
    -e BASE_URL=${params.BASE_URL} \
    -e API_KEY=${params.API_KEY} \
    -e LANG=en_US.UTF-8 \
    -e LC_ALL=en_US.UTF-8 \
    -e TZ=Asia/Shanghai \
    -w /workspace/AiAgent-test \
    ${OPENCODE_IMAGE} \
    -c "sleep infinity"

echo "=== 等待容器启动 ==="
sleep 10

echo "=== 容器状态 ==="
docker ps | grep ${containerName}

echo "=== 检查 opencode 版本 ==="
docker exec ${containerName} opencode --version || echo "opencode version check failed"

echo "=== 验证 BASE_URL 环境变量 ==="
docker exec ${containerName} sh -c 'echo "BASE_URL=\$BASE_URL"'

echo "=== 验证 opencode 配置文件 ==="
docker exec ${containerName} cat /workspace/AiAgent-test/config/opencode.json

echo "=== 测试 API 连通性 ==="
docker exec ${containerName} sh -c 'wget -q -O- --timeout=10 "\$BASE_URL/v1/models" 2>&1 || echo "API connectivity check failed"'

echo "=== 列出 opencode 可识别模型 ==="
docker exec ${containerName} sh -c 'OPENCODE_CONFIG=/workspace/AiAgent-test/config/opencode.json opencode models 2>&1 | head -30'

echo "=== 快速测试 opencode run ==="
docker exec ${containerName} sh -c 'OPENCODE_CONFIG=/workspace/AiAgent-test/config/opencode.json timeout 60 opencode run "Say hi" --model custom-openai/${env.SERVED_MODEL_NAME} --dangerously-skip-permissions 2>&1 || echo "opencode run quick test failed/timed out"'

echo "=== 检查 Python 环境 ==="
docker exec ${containerName} sh -c "python3 --version || python --version || echo 'Python not found, will install'"

echo "=== 安装 Python3（如需要）==="
docker exec ${containerName} sh -c "command -v python3 || (apk add --no-cache python3 2>/dev/null) || echo 'Python install skipped'"

ENDSSH
"""
                    }
                }
            }
        }

        stage('运行验证脚本') {
            steps {
                script {
                    def containerName = env.CONTAINER_NAME
                    def modelName = "custom-openai/${env.SERVED_MODEL_NAME}"
                    def curdate = env.CURDATE

                    println("=== 运行 OpenCode 验证脚本 ===")
                    println("模型: ${modelName}")
                    println("时间戳: ${curdate}")

                    sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                        catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                            sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e

echo "=== 确认容器运行 ==="
docker ps | grep ${containerName}

echo "=== 运行 Python 验证脚本 ==="
docker exec ${containerName} sh -c \\
    "python3 /workspace/AiAgent-test/scripts/validate_opencode.py \\
        --model '${modelName}' \\
        --config-path /workspace/AiAgent-test/config/opencode.json \\
        --work-dir /workspace/AiAgent-test \\
        --output-dir /workspace/AiAgent-test/results \\
        --timeout 300 \\
        --base-url '${params.BASE_URL}' \\
        --infra '${params.INFRA}' \\
        --chip '${params.CHIP}' \\
        --pd '${params.PD}' \\
        --tester '${params.TESTER}' \\
        --build-number '${BUILD_NUMBER}' \\
        --curdate '${curdate}'"

echo "=== 验证脚本执行完成 ==="

echo "=== 查看结果目录结构 ==="
docker exec ${containerName} find /workspace/AiAgent-test/results/${params.TESTER}/${BUILD_NUMBER} -type f || echo "Results directory not found"

ENDSSH
"""
                        }
                    }
                }
            }
        }

        stage('打包并拉取测试结果') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                        script {
                            def curdate = env.CURDATE
                            def resultRelPath = "results/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.SERVED_MODEL_NAME}/${curdate}"

                            println("=== 打包并拉取测试结果 ===")
                            println("结果路径: ${resultRelPath}")

                            sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e

echo "=== 在宿主机创建输出日志压缩包 ==="
cd ${params.WORK_DIR}/${resultRelPath}
if ls *.txt 1>/dev/null 2>&1; then
    tar czf output_logs.tar.gz *.txt
    echo "压缩包创建成功: output_logs.tar.gz"
    ls -la output_logs.tar.gz
else
    echo "没有找到 txt 文件，跳过压缩"
fi

echo "=== 结果文件列表 ==="
ls -la ${params.WORK_DIR}/${resultRelPath}/

ENDSSH
"""

                            sh """
set -e
echo "=== 拉取结果到 Jenkins workspace ==="
rm -rf results
mkdir -p results/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.SERVED_MODEL_NAME}

scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r ${REMOTE_USER}@${REMOTE_HOST}:${params.WORK_DIR}/${resultRelPath} results/${params.TESTER}/${BUILD_NUMBER}/${params.CHIP}/${env.SERVED_MODEL_NAME}/

echo "=== 拉取完成，查看文件 ==="
find results -type f
"""
                        }
                    }
                }
            }
        }

        stage('发送邮件') {
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    script {
                        def testStatus = "失败/无结果"
                        def reportHtml = '<p>未找到验证报告文件</p>'

                        def htmlFiles = findFiles(glob: "results/**/validation_report.html")
                        if (htmlFiles && htmlFiles.length > 0) {
                            reportHtml = readFile(htmlFiles[0].path)
                        }

                        def resultFiles = findFiles(glob: "results/**/validation_results.json")
                        if (resultFiles && resultFiles.length > 0) {
                            def resultContent = readFile(resultFiles[0].path)
                            def resultJson = readJSON(text: resultContent)
                            def summary = resultJson.summary
                            testStatus = summary.failed == 0 ? "成功" : "部分失败"
                        }

                        def emailBody = """
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background-color: #fff; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .header { background-color: ${testStatus == '成功' ? '#2196F3' : '#f44336'}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }
        .content { padding: 20px; }
        table { border-collapse: collapse; width: 100%; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
<div class="container">
<div class="header">
    <h2 style="margin: 0;">OpenCode CLI 验证测试报告 - 构建 #${BUILD_NUMBER}</h2>
</div>
<div class="content">
    <h3>测试概要</h3>
    <table>
        <tr><th>项目</th><td>值</td></tr>
        <tr><td>构建编号</td><td>#${BUILD_NUMBER}</td></tr>
        <tr><td>推理框架</td><td>${params.INFRA}</td></tr>
        <tr><td>芯片平台</td><td>${params.CHIP}</td></tr>
        <tr><td>PD分离模式</td><td>${params.PD}</td></tr>
        <tr><td>模型名称</td><td>${params.MODEL}</td></tr>
        <tr><td>模型路径</td><td>${params.MODEL_PATH}</td></tr>
        <tr><td>API 地址</td><td>${params.BASE_URL}</td></tr>
        <tr><td>OpenCode 镜像</td><td>${OPENCODE_IMAGE}</td></tr>
        <tr><td>测试人员</td><td>${params.TESTER}</td></tr>
        <tr><td>执行时间</td><td>${currentBuild.durationString}</td></tr>
        <tr><td>测试状态</td><td>${testStatus}</td></tr>
    </table>

    <h3>测试报告内容</h3>
    ${reportHtml}

    <p style="margin-top: 20px;"><b>详细日志和报告已归档到 Jenkins 构建 artifacts 中。</b></p>
    <p>Jenkins 构建地址: <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>
</div>
<div class="footer" style="margin-top: 20px; padding: 15px; background-color: #f9f9f9;">
    此邮件由 Jenkins 自动发送，请勿回复。
</div>
</div>
</body>
</html>"""

                        println("=== 发送邮件 ===")
                        println("测试状态: ${testStatus}")

                        emailext(
                            subject: "[模型推理 - OpenCode验证测试报告] #${BUILD_NUMBER} ${params.CHIP} - ${env.SERVED_MODEL_NAME} (${testStatus})",
                            body: emailBody,
                            to: "${params.RECIPIENTS}",
                            mimeType: 'text/html',
                            attachmentsPattern: "results/**/output_logs.tar.gz,results/**/validation_report.md"
                        )
                    }
                }
            }
        }

        stage('清理容器') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    script {
                        def containerName = env.CONTAINER_NAME ?: "opencode-validate-${params.CHIP}-${env.SERVED_MODEL_NAME}-${BUILD_NUMBER}"
                        println("=== 清理容器: ${containerName} ===")

                        sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
docker rm -f ${containerName} 2>/dev/null || true
echo "容器 ${containerName} 已删除"

echo "=== 清理旧的 results_backup 目录 ==="
rm -rf ${params.WORK_DIR}/results_backup 2>/dev/null || true

echo "清理完成"
ENDSSH
"""
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                archiveArtifacts artifacts: "results/**", allowEmptyArchive: true, fingerprint: true
                println("构建完成: ${currentBuild.currentResult}")
            }
        }
        cleanup {
            cleanWs()
        }
    }
}
