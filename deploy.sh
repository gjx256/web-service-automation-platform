#!/bin/bash

# ============================================
# Web服务自动化管理平台 - 一键部署脚本
# 适用系统：CentOS 9 / Rocky Linux 9 / RHEL 9
# ============================================

set -e  # 遇到错误立即退出

# ---------- 配置区（根据实际情况修改）----------
PROJECT_DIR="/home/gjx/mc_registry_project"
DB_ROOT_PASS="123456"           # MariaDB root 密码
DB_NAME="mc_registry"
ADMIN_PASS="123456"        # 管理后台密码
FLASK_PORT=5000
NGINX_CONF="/etc/nginx/conf.d/mc-registry.conf"
SERVICE_FILE="/etc/systemd/system/mc-registry.service"
# -----------------------------------------------

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ---------- 1. 检查 root 权限 ----------
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 sudo 或 root 用户运行此脚本"
    exit 1
fi

log_info "开始部署 Web服务自动化管理平台..."

# ---------- 2. 检查并安装系统依赖 ----------
log_info "检查系统依赖..."

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    log_warn "Python3 未安装，正在安装..."
    dnf install -y python3 python3-pip
else
    log_info "Python3 已安装: $(python3 --version)"
fi

# 检查 MariaDB
if ! command -v mysql &> /dev/null; then
    log_warn "MariaDB 未安装，正在安装..."
    dnf install -y mariadb-server mariadb
    systemctl enable mariadb --now
    # 初始化 root 密码（如果还没设）
    mysqladmin -u root password "$DB_ROOT_PASS" 2>/dev/null || true
else
    log_info "MariaDB 已安装"
    systemctl enable mariadb --now
fi

# 检查 Nginx
if ! command -v nginx &> /dev/null; then
    log_warn "Nginx 未安装，正在安装..."
    dnf install -y nginx
else
    log_info "Nginx 已安装: $(nginx -v 2>&1 | head -1)"
fi

# ---------- 3. 配置 Python 虚拟环境 ----------
log_info "配置 Python 虚拟环境..."

cd "$PROJECT_DIR" || exit 1

if [ ! -d "venv" ]; then
    log_info "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

log_info "安装 Python 依赖..."
pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
pip install flask pymysql mcrcon -i https://mirrors.aliyun.com/pypi/simple/

# ---------- 4. 初始化数据库 ----------
log_info "初始化数据库..."

mysql -u root -p"$DB_ROOT_PASS" <<EOF
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ${DB_NAME};
CREATE TABLE IF NOT EXISTS users (
    id INT(11) NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) DEFAULT NULL,
    mc_name VARCHAR(50) NOT NULL UNIQUE,
    registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
EOF

log_info "数据库和表创建完成"

# ---------- 5. 更新 app.py 中的管理员密码 ----------
log_info "更新管理员密码..."
sed -i "s/ADMIN_PASS = '.*'/ADMIN_PASS = '${ADMIN_PASS}'/" app.py
log_info "管理员密码已设置为: ${ADMIN_PASS}"

# ---------- 6. 配置 Systemd 服务 ----------
log_info "配置 Systemd 服务..."

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Web Service Automation Platform (Flask)
After=network.target mariadb.service

[Service]
Type=simple
User=gjx
Group=gjx
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin"
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mc-registry

log_info "Systemd 服务配置完成"

# ---------- 7. 配置 Nginx 反向代理 ----------
log_info "配置 Nginx 反向代理..."

# 移除默认站点（防止覆盖）
if [ -f /etc/nginx/conf.d/default.conf ]; then
    mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak
    log_info "已备份默认 Nginx 站点配置"
fi

cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name _;  # 监听所有域名

    location / {
        proxy_pass http://127.0.0.1:${FLASK_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
EOF

nginx -t
systemctl enable nginx --now

log_info "Nginx 配置完成并启动"

# ---------- 8. 启动 Flask 服务 ----------
log_info "启动 Flask 应用..."
systemctl restart mc-registry
sleep 2

# ---------- 9. 验证状态 ----------
log_info "验证服务状态..."

if systemctl is-active --quiet mc-registry; then
    log_info "Flask 服务运行正常 (mc-registry)"
else
    log_error "Flask 服务启动失败，请检查日志: journalctl -u mc-registry -n 50"
    exit 1
fi

if systemctl is-active --quiet nginx; then
    log_info "Nginx 运行正常"
else
    log_error "Nginx 启动失败"
    exit 1
fi

if systemctl is-active --quiet mariadb; then
    log_info "MariaDB 运行正常"
else
    log_error "MariaDB 启动失败"
    exit 1
fi

# 检查端口
if ss -tlnp | grep -q ":80 "; then
    log_info "端口 80 (Nginx) 监听正常"
fi

if ss -tlnp | grep -q ":${FLASK_PORT} "; then
    log_info "端口 ${FLASK_PORT} (Flask) 监听正常"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "访问地址:"
echo "  用户注册页: http://你的服务器IP/"
echo "  管理后台:   http://你的服务器IP/admin?pwd=${ADMIN_PASS}"
echo ""
echo "常用命令:"
echo "  查看 Flask 日志:  sudo journalctl -u mc-registry -f"
echo "  重启服务:         sudo systemctl restart mc-registry"
echo "  查看服务状态:     sudo systemctl status mc-registry"
echo "  重载 Nginx:       sudo nginx -s reload"
echo ""
