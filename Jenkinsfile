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
        text(name: 'RECIPIENTS', defaultValue: 'liwt@zetyun.com', description: '邮件接收者（逗号分隔）')
        string(name: 'WORK_DIR', defaultValue: '/dingofs/data1/userdata/liwt/maas-image/AiAgent-test', description: '测试仓库目录，请不要修改')
    }
    environment {
        SSH_CREDENTIALS = 'HOST_SSH_KEY'
        REMOTE_HOST = '10.201.132.50'
        REMOTE_USER = 'root'
        OPENCODE_IMAGE = 'ghcr.io/anomalyco/opencode:1.17.0'
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
                    def safeModel = params.MODEL.replaceAll('\\.', '-').replaceAll('_', '-')
                    def containerName = "opencode-validate-${params.CHIP}-${safeModel}-${BUILD_NUMBER}"
                    env.CONTAINER_NAME = containerName

                    println("=== 启动 opencode 容器 ===")
                    println("容器名: ${containerName}")

                    sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                        sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e

echo "=== 清理旧容器 ==="
docker rm -f ${containerName} 2>/dev/null || true

echo "=== 检查配置文件 ==="
cat ${params.WORK_DIR}/config/opencode.json

echo "=== 启动 opencode 容器 ==="
docker run -d --name ${containerName} \
    --network host \
    --entrypoint sh \
    -v ${params.WORK_DIR}:/workspace/AiAgent-test \
    -e OPENCODE_CONFIG=/workspace/AiAgent-test/config/opencode.json \
    -e BASE_URL=${params.BASE_URL} \
    -e LANG=en_US.UTF-8 \
    -e LC_ALL=en_US.UTF-8 \
    -w /workspace/AiAgent-test \
    ${OPENCODE_IMAGE} \
    -c "sleep infinity"

echo "=== 等待容器启动 ==="
sleep 10

echo "=== 容器状态 ==="
docker ps | grep ${containerName}

echo "=== 检查 opencode 版本 ==="
docker exec ${containerName} opencode --version || echo "opencode version check failed"

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
                    def modelName = "openai/${params.MODEL}"

                    println("=== 运行 OpenCode 验证脚本 ===")
                    println("模型: ${modelName}")

                    sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                        catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                            sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e

echo "=== 确认容器运行 ==="
docker ps | grep ${containerName}

echo "=== 预检查: 验证 opencode 配置 ==="
docker exec ${containerName} cat /workspace/AiAgent-test/config/opencode.json

echo "=== 预检查: 验证 BASE_URL 环境变量 ==="
docker exec ${containerName} sh -c 'echo "BASE_URL=\$BASE_URL"'

echo "=== 预检查: 测试 API 连通性 ==="
docker exec ${containerName} sh -c 'wget -q -O- --timeout=10 "\${BASE_URL}/v1/models" 2>&1 || curl -s --connect-timeout 10 "\${BASE_URL}/v1/models" 2>&1 || echo "API connectivity check failed (no wget/curl)"'

echo "=== 预检查: 验证 opencode 可识别模型 ==="
docker exec ${containerName} sh -c 'OPENCODE_CONFIG=/workspace/AiAgent-test/config/opencode.json opencode models 2>&1 | head -30'

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
        --tester '${params.TESTER}'"

echo "=== 验证脚本执行完成 ==="

echo "=== 查看结果文件 ==="
docker exec ${containerName} ls -la /workspace/AiAgent-test/results/ || echo "Results directory not found"

ENDSSH
"""
                        }
                    }
                }
            }
        }

        stage('拉取测试结果') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                        script {
                            def containerName = env.CONTAINER_NAME
                            def buildsDir = "builds/${BUILD_NUMBER}"

                            println("=== 拉取测试结果到 Jenkins workspace ===")

                            sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
set -e

echo "=== 从容器中复制结果到宿主机 ==="
mkdir -p ${params.WORK_DIR}/results_backup/${BUILD_NUMBER}
docker cp ${containerName}:/workspace/AiAgent-test/results/. ${params.WORK_DIR}/results_backup/${BUILD_NUMBER}/

echo "=== 结果文件列表 ==="
ls -la ${params.WORK_DIR}/results_backup/${BUILD_NUMBER}/

echo "=== 验证结果 JSON ==="
cat ${params.WORK_DIR}/results_backup/${BUILD_NUMBER}/validation_results.json || echo "No validation_results.json found"

ENDSSH
"""

                            sh """
set -e
echo "=== 拉取结果到 Jenkins workspace ==="
rm -rf ${buildsDir}
mkdir -p ${buildsDir}

scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r ${REMOTE_USER}@${REMOTE_HOST}:${params.WORK_DIR}/results_backup/${BUILD_NUMBER}/ ./${buildsDir}/

echo "=== 拉取完成，查看文件 ==="
find ./${buildsDir} -type f
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
                        def buildsDir = "builds/${BUILD_NUMBER}"
                        def testStatus = "失败/无结果"
                        def reportHtml = ""

                        def resultFile = findFiles(glob: "${buildsDir}/validation_results.json")
                        if (resultFile && resultFile.length > 0) {
                            def resultContent = readFile(resultFile[0].path)
                            def resultJson = readJSON(text: resultContent)
                            def summary = resultJson.summary
                            testStatus = summary.failed == 0 ? "成功" : "部分失败"

                            for (def test : resultJson.tests) {
                                def statusLabel = test.passed ? "PASSED" : "FAILED"
                                def escapedOutput = test.output_preview
                                    .replace('&', '&amp;')
                                    .replace('<', '&lt;')
                                    .replace('>', '&gt;')
                                    .replace('\n', '<br/>')

                                def issuesHtml = ""
                                if (test.issues && test.issues.size() > 0) {
                                    issuesHtml = "<ul>" + test.issues.collect { "<li>${it}</li>" }.join('') + "</ul>"
                                }

                                reportHtml += """
                                    <div class="report-block">
                                        <h3 style="margin-top:0;color:${test.passed ? '#4CAF50' : '#f44336'};">
                                            ${test.test_name} - ${statusLabel}
                                        </h3>
                                        ${issuesHtml}
                                        <div class="report-content">
                                            <pre>${escapedOutput}</pre>
                                        </div>
                                    </div>
                                """
                            }
                        } else {
                            reportHtml = '<p>未找到验证结果文件</p>'
                        }

                        def mdFiles = findFiles(glob: "${buildsDir}/**/*.md")
                        if (mdFiles && mdFiles.length > 0) {
                            for (def mdFile : mdFiles) {
                                def mdContent = readFile(mdFile.path)
                                def escapedMd = mdContent
                                    .replace('&', '&amp;')
                                    .replace('<', '&lt;')
                                    .replace('>', '&gt;')
                                    .replace('\n', '<br/>')
                                reportHtml += """
                                    <div class="report-block">
                                        <h3 style="color:#2196F3;">${mdFile.name}</h3>
                                        <pre style="background:#f4f4f4;border:1px solid #ddd;border-radius:4px;padding:12px;overflow-x:auto;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-all;">${escapedMd}</pre>
                                    </div>
                                """
                            }
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
        .report-block { margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; background-color: #fafafa; border-radius: 5px; }
        .report-content pre { background:#f4f4f4;border:1px solid #ddd;border-radius:4px;padding:12px;overflow-x:auto;margin:10px 0;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-all; }
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
                            subject: "[OpenCode验证测试报告] #${BUILD_NUMBER} ${params.CHIP} - ${params.MODEL} (${testStatus})",
                            body: emailBody,
                            to: "${params.RECIPIENTS}",
                            mimeType: 'text/html',
                            attachmentsPattern: "builds/${BUILD_NUMBER}/**"
                        )
                    }
                }
            }
        }

        stage('清理容器') {
            steps {
                sshagent(credentials: ["${SSH_CREDENTIALS}"]) {
                    script {
                        def containerName = env.CONTAINER_NAME ?: "opencode-validate-${params.CHIP}-${params.MODEL}-${BUILD_NUMBER}"
                        println("=== 清理容器: ${containerName} ===")

                        sh """
ssh -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} << 'ENDSSH'
docker rm -f ${containerName} 2>/dev/null || true
echo "容器 ${containerName} 已删除"

echo "=== 清理宿主机备份结果 ==="
rm -rf ${params.WORK_DIR}/results_backup/${BUILD_NUMBER} 2>/dev/null || true

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
                archiveArtifacts artifacts: "builds/${BUILD_NUMBER}/**", allowEmptyArchive: true, fingerprint: true
                println("构建完成: ${currentBuild.currentResult}")
            }
        }
        cleanup {
            cleanWs()
        }
    }
}
