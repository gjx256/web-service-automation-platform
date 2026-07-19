# Web Service Automation Platform (MC Registry)

一个轻量级的 Web 服务自动化管理平台，旨在实现 Minecraft 服务器白名单的自动化注册、数据持久化与远程指令下发，覆盖从 Web 端到服务端配置的完整 DevOps 闭环。

## 🌟 核心特性
- **全链路自动化**：用户 Web 端注册 -> 数据库持久化 -> RCON 远程下发白名单 -> 服务端配置热重载。
- **一键自动化部署**：提供 `deploy.sh` 脚本，一键完成环境检测、依赖安装、数据库初始化、Systemd 服务编排及 Nginx 配置。
- **高可用进程守护**：基于 Systemd 实现应用与游戏服务端的开机自启与崩溃自动重启。
- **反向代理与隔离**：使用 Nginx 进行端口转发，隐藏后端真实端口，提升安全性。

## 🛠️ 技术栈
- **OS**: CentOS 9 Stream
- **Backend**: Python 3 + Flask
- **Database**: MariaDB
- **Proxy**: Nginx
- **Process**: Systemd
- **Automation**: Shell (Bash)

## 🚀 快速开始
bash
git clone https://github.com/gjx256/web-service-automation-platform.git
cd web-service-automation-platform
chmod +x deploy.sh
sudo ./deploy.sh

##⚙️ 环境变量配置
生产环境请通过 .env 文件或 Systemd 的 EnvironmentFile 注入敏感信息，切勿硬编码。

##  📄 License
MIT License EOF
