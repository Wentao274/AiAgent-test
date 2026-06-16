# 1. 指定基础镜像
FROM ghcr.io/anomalyco/opencode:1.17.0

# 2. 安装 Python3 及常用工具
# OpenCode 基础镜像基于 Alpine，使用 apk 包管理器
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    git \
    curl \
    # 如果后续需要编译某些 Python 库，可能还需要以下依赖：
    # python3-dev \
    # gcc \
    # musl-dev \
    && ln -sf python3 /usr/bin/python \
    && ln -sf pip3 /usr/bin/pip

# 3. (可选) 设置工作目录
WORKDIR /workspace

# 4. (可选) 如果你希望容器启动后直接进入 bash 以便调试，可以覆盖默认入口
# 注意：OpenCode 默认可能直接启动 TUI，改为 bash 后你需要手动输入 'opencode' 启动
#CMD ["bash"]
