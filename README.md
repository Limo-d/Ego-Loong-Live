# Ego-Loong Live

Ego-Loong Live 是一套面向第一视角数据采集的实时网页可视化系统，用一个页面集中显示：

- 第一视角 RGB 画面
- 左右手 68 点触觉
- 左右手实时手部姿态

后端使用 ROS 2、FastAPI 和 WebSocket，前端使用原生 JavaScript、Canvas 与 Three.js。项目支持真实设备模式和不依赖 ROS Topic 的 Mock 模式。

本文档以“拿到一台全新的 Ubuntu 笔记本，如何从零部署并连接设备”为主线，同时覆盖四设备、四大屏部署、网络优化和故障排查。

> 当前架构边界：一个后端实例订阅一套设备的一路 RGB 和一路 `HandFrame`。多设备需要多个后端实例。结合当前负载情况，四设备、四大屏建议使用两台笔记本，每台运行两个实例。

## 1. 系统架构

```text
设备端 ROS 2 节点
  ├─ RGB CompressedImage ─┐
  └─ HandFrame ───────────┼─ Zenoh Router ─ 笔记本 ROS 2 Client
                         │                 ├─ 最新帧缓存
                         │                 ├─ RGB/JPEG 处理
                         │                 ├─ 68 点触觉处理
                         │                 ├─ 手部正向运动学
                         │                 └─ FastAPI/WebSocket
                         └──────────────────────── 浏览器页面
```

后端只保留最新 ROS 帧，RGB 使用 Best Effort、Keep Last、默认深度 1，避免无线抖动时积压旧画面。慢浏览器客户端同样只保留各通道最新待发送数据。

### 1.1 默认数据接口

默认配置文件为 `config/config.yaml`。

| 数据 | Topic | 消息类型 | 默认处理上限 |
| --- | --- | --- | --- |
| RGB | `/factor_perception/rgb/image_rect/compressed` | `sensor_msgs/msg/CompressedImage` | 30 FPS |
| 双手触觉与姿态 | `/hand_frame` | `hand_frame/msg/HandFrame` | 触觉 30 FPS，姿态 60 FPS |

`HandFrame` 同时包含：

- `pressure_left[68]`、`pressure_right[68]`
- `solve_state_left[27]`、`solve_state_right[27]`
- 左右手 IMU、压力时间戳

自定义消息源码位于 `hand_msg_ws/src/hand_frame`。新电脑上必须重新编译，不能直接复用另一台电脑生成的 `build/`、`install/` 和 `log/`。

### 1.2 网页地址

单实例默认监听 `0.0.0.0:8000`：

- 开始页：`http://localhost:8000/`
- 实时页面：`http://localhost:8000/dashboard`
- 健康检查：`http://localhost:8000/api/health`
- 系统状态：`http://localhost:8000/api/status`
- WebSocket：`ws://localhost:8000/ws`

## 2. 推荐硬件和软件

### 2.1 单台笔记本同时显示两套设备

推荐配置：

- CPU：8 核或以上的标压处理器
- 内存：最低 16 GB，推荐 32 GB
- GPU：支持 WebGL 2 和浏览器硬件加速，独立显卡更稳
- 网络：千兆网口，或可靠的 USB-C 转千兆网卡
- 显示：两个独立扩展输出，例如 HDMI + USB-C/DP
- 磁盘：至少预留 10 GB

HDMI 分配器通常只能复制同一画面。四块大屏要显示四套设备，应使用操作系统的“扩展桌面”，每块屏幕放置独立浏览器窗口。

### 2.2 已验证的软件基线

- Ubuntu 24.04 LTS 64-bit
- ROS 2 Jazzy
- Python 3.12（Ubuntu 系统 Python）
- `rmw_zenoh_cpp`
- Chrome/Chromium 或其他支持 WebGL 2 的现代浏览器

项目运行不需要 Node.js、npm、CUDA 或 PyTorch。Three.js 已保存在 `frontend/vendor/`，页面不依赖外部 CDN。

ROS 2 Jazzy 官方支持 Ubuntu 24.04；安装 ROS 软件源时以 [ROS 2 Jazzy Ubuntu 安装文档](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) 为准。Zenoh 的 Client、Router 和配置覆盖方式见 [ros2/rmw_zenoh](https://github.com/ros2/rmw_zenoh)。

## 3. 新笔记本从零部署

下面假设仓库最终位于：

```text
/home/<用户名>/Ego-Loong-Live
```

请将命令中的 `<用户名>`、`<repository-url>` 和设备 IP 替换成现场实际值。

### 3.1 安装 Ubuntu 和基础工具

安装 Ubuntu 24.04 后先更新系统：

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git curl software-properties-common netcat-openbsd
```

确认系统架构和版本：

```bash
uname -m
lsb_release -a
```

推荐 `x86_64`/`amd64` 笔记本。系统版本应为 Ubuntu 24.04（Noble）。

### 3.2 安装 ROS 2 Jazzy

先按照 ROS 官方文档添加 ROS 2 apt 软件源，然后安装本项目需要的包：

```bash
sudo apt update
sudo apt install -y \
  ros-jazzy-ros-base \
  ros-jazzy-rmw-zenoh-cpp \
  ros-jazzy-rclpy \
  ros-jazzy-sensor-msgs \
  ros-jazzy-rosidl-default-generators \
  ros-jazzy-rosidl-default-runtime \
  python3.12-venv \
  python3-pip \
  python3-numpy \
  python3-opencv \
  python3-colcon-common-extensions \
  build-essential cmake
```

验证 ROS：

```bash
source /opt/ros/jazzy/setup.bash
ros2 --help
```

不要用 Conda Python 替换 `/usr/bin/python3`。ROS 2 apt 包和 Conda Python 混用容易产生 `rclpy`、NumPy 或自定义消息 ABI 问题。

### 3.3 获取仓库

使用 Git：

```bash
cd ~
git clone <repository-url> Ego-Loong-Live
cd Ego-Loong-Live
```

也可以从移动硬盘复制源码。迁移时只保留源码，不要复制旧电脑的机器相关产物：

```text
.venv/
hand_msg_ws/build/
hand_msg_ws/install/
hand_msg_ws/log/
**/__pycache__/
```

如果这些目录已经随仓库复制过来，先删除后再安装：

```bash
rm -rf .venv hand_msg_ws/build hand_msg_ws/install hand_msg_ws/log
find . -type d -name __pycache__ -prune -exec rm -rf {} +
```

### 3.4 一键安装项目环境

```bash
cd ~/Ego-Loong-Live
chmod +x scripts/*.sh
./scripts/install.sh
```

安装脚本会：

1. 使用 `/usr/bin/python3` 创建带系统包访问能力的 `.venv`。
2. 安装 FastAPI、Uvicorn、PyYAML、psutil 和 websockets。
3. 使用 ROS 2 Jazzy 编译本地 `hand_frame` 消息包。
4. 验证 `rclpy` 和 `hand_frame/msg/HandFrame` 可以导入。
5. 检查网页和配置文件是否完整。

安装成功时应看到：

```text
ROS 2 + hand_frame: OK
Install complete. Run: ./scripts/run_mock.sh
```

手动验证：

```bash
source /opt/ros/jazzy/setup.bash
source hand_msg_ws/install/setup.bash
.venv/bin/python -c 'import rclpy, cv2, numpy; from hand_frame.msg import HandFrame; print("OK")'
```

### 3.5 先用 Mock 模式验收笔记本

Mock 模式不连接设备，先验证 Python、网页、WebSocket 和 WebGL：

```bash
cd ~/Ego-Loong-Live
./scripts/run_mock.sh
```

浏览器打开：

```text
http://localhost:8000/dashboard
```

应看到 RGB 模拟画面、双手触觉和双手姿态。若手部页面提示 WebGL 不可用：

1. 打开浏览器设置中的“使用硬件加速”。
2. 重启浏览器。
3. 在 Chrome 中打开 `chrome://gpu`，确认 WebGL 未被禁用。
4. 更新显卡驱动或切换到 Xorg 会话再次测试。

按 `Ctrl+C` 停止 Mock 服务。

### 3.6 连接设备网络

当前现场设备 Zenoh Router 默认地址为：

```text
tcp/192.168.3.13:7447
```

首先确认笔记本和设备在同一网段：

```bash
ip -4 address
ip -4 route
ping -c 4 192.168.3.13
nc -vz 192.168.3.13 7447
```

预期：

- 笔记本具有 `192.168.3.x/24` 地址。
- `ping` 能到达设备。
- `7447/tcp` 可连接。

如果设备 IP 以后变化，不建议直接编辑 `scripts/run.sh`，启动时覆盖 endpoint 即可：

```bash
EGO_ZENOH_ROUTER_ENDPOINT=tcp/<设备IP>:7447 ./scripts/run.sh
```

### 3.7 验证 ROS Topic

诊断终端必须使用和正式服务相同的 RMW/Zenoh 配置：

```bash
cd ~/Ego-Loong-Live
source /opt/ros/jazzy/setup.bash
source hand_msg_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='mode="client";connect/endpoints=["tcp/192.168.3.13:7447"]'

ros2 topic list -t
ros2 topic hz /factor_perception/rgb/image_rect/compressed
ros2 topic hz /hand_frame
```

也可以运行仓库脚本：

```bash
./scripts/check_topics.sh
```

应发现：

```text
/factor_perception/rgb/image_rect/compressed [sensor_msgs/msg/CompressedImage]
/hand_frame [hand_frame/msg/HandFrame]
```

### 3.8 启动真实设备模式

默认设备地址已经写为 `192.168.3.13`：

```bash
cd ~/Ego-Loong-Live
./scripts/run.sh
```

打开：

```text
http://localhost:8000/dashboard
```

从同一局域网的其他电脑访问时，使用笔记本 IP：

```text
http://<笔记本IP>:8000/dashboard
```

如果 Ubuntu 防火墙已启用：

```bash
sudo ufw allow 8000/tcp
```

### 3.9 首次真实设备验收

按顺序检查：

1. RGB 连续显示，画面宽高比正确，没有裁剪。
2. 左右手触觉在空载基线完成后能响应按压。
3. 左右手姿态分别跟随各自手套，不发生数据同步或串手。
4. 蓝色左手位于画面左侧，粉色右手位于画面右侧。
5. 右手拇指位于右手手掌的屏幕左侧。
6. `/api/status` 中 RGB、触觉、姿态通道均未超时。
7. 连续运行至少 30 分钟，没有逐渐增加的画面延迟。

### 3.10 Docker 镜像部署（推荐用于快速迁移）

仓库提供基于 Ubuntu 24.04 和 ROS 2 Jazzy 的 `Dockerfile`，包含 ROS、Python
依赖、自定义消息、前后端、默认配置及左右手触觉标定文件。当前镜像标签为
`ge89jar/ego-loong-live:0714`。

```bash
cd ~/Ego-Loong-Live
docker build -t ge89jar/ego-loong-live:0714 .
```

先用 Mock 模式验收容器，不依赖真实设备：

```bash
docker run --rm --name ego-loong-live-mock \
  -p 8000:8000 \
  ge89jar/ego-loong-live:0714 \
  python -m backend.main --mock
```

打开 `http://localhost:8000/dashboard`。真实设备模式推荐 Linux 使用宿主网络，ROS 2 和 Zenoh 网络行为最直接：

```bash
docker run --rm --name ego-loong-live \
  --network host \
  -e EGO_ZENOH_ROUTER_ENDPOINT=tcp/192.168.3.13:7447 \
  ge89jar/ego-loong-live:0714
```

使用 `--network host` 时不需要 `-p 8000:8000`。如设备 IP 改变，只改 `EGO_ZENOH_ROUTER_ENDPOINT`，无需重新构建镜像。

如需使用独立设备配置或新标定文件，通过 `-v` 挂载到容器内的 `config/`；
否则修改配置后重新构建镜像。

后台运行和查看日志：

```bash
docker run -d --restart unless-stopped --name ego-loong-live \
  --network host \
  -e EGO_ZENOH_ROUTER_ENDPOINT=tcp/192.168.3.13:7447 \
  ge89jar/ego-loong-live:0714

docker logs -f ego-loong-live
docker stop ego-loong-live
```

需要把已经构建好的镜像离线复制到另一台笔记本时：

```bash
# 原电脑导出
docker save ge89jar/ego-loong-live:0714 | gzip > ego-loong-live-0714.tar.gz

# 将文件复制到新电脑后导入
gunzip -c ego-loong-live-0714.tar.gz | docker load
```

导入后直接执行上面的 `docker run` 命令，不需要再次安装 ROS 2 或 Python 依赖。

## 4. 启动参数与配置

### 4.1 常用启动方式

```bash
# 默认真实设备
./scripts/run.sh

# 指定另一个设备 Zenoh Router
EGO_ZENOH_ROUTER_ENDPOINT=tcp/192.168.10.11:7447 ./scripts/run.sh

# 指定配置文件
EGO_LOONG_LIVE_CONFIG=config/device01.yaml ./scripts/run.sh

# 临时改 Web 端口
EGO_LOONG_LIVE_PORT=8001 ./scripts/run.sh

# Mock 模式
./scripts/run_mock.sh
```

### 4.2 环境变量

| 变量 | 作用 |
| --- | --- |
| `EGO_LOONG_LIVE_CONFIG` | 指定 YAML 配置文件 |
| `EGO_LOONG_LIVE_HOST` | 覆盖 Web 监听地址 |
| `EGO_LOONG_LIVE_PORT` | 覆盖 Web 端口 |
| `EGO_LOONG_LIVE_MOCK` | `true/false` 强制 Mock 开关 |
| `EGO_ZENOH_ROUTER_ENDPOINT` | 设备 Zenoh Router，例如 `tcp/192.168.3.13:7447` |
| `RMW_IMPLEMENTATION` | 默认由 `run.sh` 设置为 `rmw_zenoh_cpp` |
| `ZENOH_SESSION_CONFIG_URI` | 使用完整 Zenoh Session 配置文件 |
| `ZENOH_CONFIG_OVERRIDE` | 直接覆盖 Zenoh 配置字段 |

若已经设置 `ZENOH_SESSION_CONFIG_URI` 或 `ZENOH_CONFIG_OVERRIDE`，`run.sh` 不会再生成默认 Client 配置。

### 4.3 `config/config.yaml` 关键字段

| 字段 | 说明 |
| --- | --- |
| `server.host/port` | Web 监听地址和端口 |
| `mode.mock` | 是否使用模拟数据 |
| `ros.domain_id` | 后端启动 ROS 节点前设置的 `ROS_DOMAIN_ID` |
| `topics.rgb` | RGB Topic 名称和消息类型 |
| `topics.hand` | `HandFrame` Topic 名称和类型 |
| `rgb.max_fps` | RGB 后端处理上限 |
| `rgb.queue_depth` | RGB ROS 队列深度；低延迟建议保持 1 |
| `rgb.jpeg_quality` | 后端 JPEG 编码质量，默认 75 |
| `rgb.passthrough_compressed` | JPEG 输入是否直接透传 |
| `rgb.allow_crop` | 必须为 `false`，项目禁止裁剪 RGB |
| `hand.geometry_config` | 手型骨长、根部偏移和姿态校正配置 |
| `hand.freeze_palm_orientation` | 固定腕部/手掌整体姿态 |
| `tactile.noise_gate` | 触觉噪声门限，越小越灵敏 |
| `tactile.display_deadzone` | 触觉显示死区；低于该值的空载残差不着色 |
| `tactile.ema_rise/fall` | 触觉上升和回落平滑系数 |
| `tactile.bend_decoupling` | 按 14 维关节姿态匹配空手模板并消除弯曲伪压力；左右手使用独立标定文件 |
| `timeout.*` | 各数据通道断流判定时间 |

手部配置位于 `config/retarget_hand_config.reference.json`。其中：

- `bones_mm`：各段骨长。
- `mcp_offsets_mm`：指根相对腕部的位置。
- `palm_mount_corr_deg`：只校正手指链姿态，不移动指根位置。
- `left_mcp_swing_offsets_deg`：左手指定手指的 MCP 侧摆零位偏置；未列出的手指不扣除零位。
- `left_mcp_swing_limits_deg`：左手指定手指的 MCP 侧摆有效角范围，单位为度。
- 右手使用自己的 `solve_state_right`，与左手共用运动学逻辑，不复制左手数据。

左手四指侧摆按以下顺序进入可视化 FK：

```text
有效侧摆角 = clamp(原始 MCP 侧摆角 - 零位偏置, 下限, 上限)
```

当前现场参数为：

| 手指 | 零位偏置 | 有效角范围 | 说明 |
| --- | ---: | ---: | --- |
| 食指 `index` | `0°` | `[-15°, 25°]` | 保留原始方向和向右侧摆能力，仅限制极值 |
| 中指 `middle` | `20°` | `[-10°, 10°]` | 先消除正向零位偏置，再限制相对摆幅 |
| 无名指 `ring` | `10.7°` | `[-10°, 10°]` | 先消除正向零位偏置，再限制相对摆幅 |
| 小拇指 `little` | `0°` | `[-15°, 10°]` | 保留原始方向，限制两侧极值 |

这些参数只修改左手生成 FK 点时使用的角度。WebSocket 负载中 `angles` 字段仍保留设备原始角，右手也不应用上述校正。修改 `geometry_config` 后需要重启服务。

## 5. Wi-Fi、SSH 与延迟优化

### 5.1 设备连接 Wi-Fi

在设备端查看无线网卡：

```bash
nmcli device status
nmcli radio wifi
```

连接 Wi-Fi：

```bash
sudo nmcli radio wifi on
sudo nmcli device wifi connect "<SSID>" password "<密码>" ifname wlan0
```

查看无线 IP：

```bash
ip -4 address show wlan0
ip -4 route
```

从笔记本通过无线 IP 登录：

```bash
ssh <用户名>@<设备无线IP>
```

拔网线前，必须先从另一个终端确认无线 IP 能 ping 通并能建立新的 SSH 会话。不要用设备自身执行 `ip route get <设备自己的IP>` 判断远端链路，该命令只会显示本地回环路由。

### 5.2 关闭 Wi-Fi 省电

实时 RGB 对省电唤醒比较敏感。设备端临时关闭：

```bash
sudo iw dev wlan0 set power_save off
iw dev wlan0 get power_save
```

使用 NetworkManager 持久关闭：

```bash
sudo nmcli connection modify "<连接名称>" 802-11-wireless.powersave 2
sudo nmcli connection down "<连接名称>"
sudo nmcli connection up "<连接名称>"
```

`nmcli device reapply wlan0` 可能无法热更新省电字段，此时断开并重新激活连接即可。执行前确保有本地终端或有线备用连接，避免 SSH 中断后无法重新登录。

### 5.3 检查无线链路

```bash
iw dev wlan0 link
nmcli -f IN-USE,SSID,SIGNAL,RATE,CHAN,BARS device wifi list ifname wlan0
```

建议：

- 优先使用 5 GHz、80 MHz 信道。
- 正式展示优先使用千兆有线网络。
- 避免四路 RGB 集中走拥挤的 2.4 GHz Wi-Fi。
- 为设备设置 DHCP 地址保留，防止重启后 IP 和 Zenoh endpoint 改变。

### 5.4 分层判断 RGB 延迟

先检查 ROS 源头：

```bash
ros2 topic hz /factor_perception/rgb/image_rect/compressed
ros2 topic bw /factor_perception/rgb/image_rect/compressed
ros2 topic delay /factor_perception/rgb/image_rect/compressed
```

然后检查网页状态：

```bash
curl http://localhost:8000/api/status
```

判断原则：

- ROS Topic 已有高延迟：检查相机编码、设备 CPU、无线链路和 Zenoh。
- ROS Topic 正常、网页延迟：检查笔记本 CPU、JPEG 重编码和浏览器硬件加速。
- 延迟每隔一段时间突然增加再恢复：重点检查 Wi-Fi 省电、丢包重传、设备编码阻塞。
- 延迟持续累积：检查是否有其他订阅端或中间层使用了大队列。

## 6. 四设备、四大屏部署

### 6.1 推荐拓扑

```text
设备 01 ─┐                    ┌─ 大屏 1：设备 01
设备 02 ─┼─ 千兆路由/交换机 ─ 笔记本 A
设备 03 ─┼─ 有线局域网         └─ 大屏 2：设备 02
设备 04 ─┘
                              ┌─ 大屏 3：设备 03
                           笔记本 B
                              └─ 大屏 4：设备 04
```

建议端口：

| 电脑 | 设备 | 后端端口 | 页面 |
| --- | --- | --- | --- |
| 笔记本 A | `device01` | 8001 | `http://localhost:8001/dashboard` |
| 笔记本 A | `device02` | 8002 | `http://localhost:8002/dashboard` |
| 笔记本 B | `device03` | 8001 | `http://localhost:8001/dashboard` |
| 笔记本 B | `device04` | 8002 | `http://localhost:8002/dashboard` |

### 6.2 使用 ROS Domain 隔离同名 Topic

物理路由器只负责 IP 通信，不会自动区分同名 ROS Topic。当前设备继续使用固定 Topic 名称，采用不同 `ROS_DOMAIN_ID` 隔离：

| 设备 | `ROS_DOMAIN_ID` | 配置文件 | Web 端口 |
| --- | ---: | --- | ---: |
| `device01` | 11 | `config/device01.yaml` | 8001 |
| `device02` | 12 | `config/device02.yaml` | 8002 |

设备端必须在启动 ROS 2 发布节点之前设置对应 Domain：

```bash
# 设备 01
export ROS_DOMAIN_ID=11
ros2 run <package> <node>
```

```bash
# 设备 02
export ROS_DOMAIN_ID=12
ros2 run <package> <node>
```

上位机容器从各自 YAML 的 `ros.domain_id` 读取相同值。两个容器可以连接同一个 Zenoh Router，Domain 会隔离 ROS 图中的同名 `/hand_frame` 和 RGB Topic。只启动两个容器但让设备和容器都留在 Domain 0 不会产生隔离，消息仍会交错。

### 6.3 一台笔记本启动两个 Docker 实例

仓库已提供完整的 `config/device01.yaml`、`config/device02.yaml` 和管理脚本：

```bash
chmod +x scripts/docker_dual.sh
./scripts/docker_dual.sh start
./scripts/docker_dual.sh status
```

默认镜像为 `ge89jar/ego-loong-live:0715`。测试部署中，`device01` 默认连接 `tcp/192.168.1.110:7447`，`device02` 默认连接 `tcp/192.168.1.107:7447`。现场地址不同时可以分别覆盖：

```bash
DEVICE01_ZENOH_ROUTER_ENDPOINT=tcp/<device01-ip>:7447 \
DEVICE02_ZENOH_ROUTER_ENDPOINT=tcp/<device02-ip>:7447 \
./scripts/docker_dual.sh start
```

如果之后改为两台设备共同使用一个集中式 Zenoh Router：

```bash
EGO_ZENOH_ROUTER_ENDPOINT=tcp/<router-ip>:7447 \
./scripts/docker_dual.sh start
```

常用管理命令：

```bash
./scripts/docker_dual.sh logs 1
./scripts/docker_dual.sh logs 2
./scripts/docker_dual.sh restart
./scripts/docker_dual.sh stop
```

页面地址为 `http://localhost:8001/dashboard` 和 `http://localhost:8002/dashboard`。管理脚本会覆盖镜像原来固定检查 8000 端口的健康检查，分别检查 8001 和 8002。

## 7. 性能建议

两实例同时运行时：

- 笔记本接通电源，并将 Ubuntu 电源模式设为“性能”。
- 开启浏览器硬件加速。
- 每个实例只订阅自己负责的设备 Topic。
- RGB 队列保持 1，不要通过增大队列解决丢帧。
- 优先保持 30 FPS；CPU 或带宽不足时先将 JPEG 质量从 75 降到 65～70。
- 不建议通过裁剪或强制拉伸降低负载，这会改变第一视角画面。
- 正式展示前同时运行两设备、两网页至少 1 小时。

RGB 为 JPEG 输入且设备编码可直接用于浏览器时，可以测试：

```yaml
rgb:
  passthrough_compressed: true
```

这会减少一次 JPEG 重编码，但必须确认输入 `format` 是 JPEG、画面兼容且带宽稳定。

## 8. 触觉与手部姿态说明

### 8.1 触觉

- 每手 68 点：五指 20 点，手掌 48 点。
- 每次启动的前 24 帧为空载零压力标定，此时保持双手自然展开且不要按压。
- 左右手分别使用 `config/tactile/joint_decouple_calib_left.npz` 和
  `joint_decouple_calib_right.npz`，弯曲模板无需每次启动重采。
- `contact_threshold` 和 `display_deadzone` 默认均为 `3.0`，低于死区及零压力的点不着色。
- 姿态超出模板范围时会退回普通零点基线；如频繁发生，应重新采集完整屈伸范围。
- 调低 `noise_gate` 或调高 `ema_rise` 可提高灵敏度，但不要将 `noise_gate` 设为 0。

重新标定时不要接触物体，在默认 12 秒内缓慢完成伸直到握拳：

```bash
source /opt/ros/jazzy/setup.bash
source hand_msg_ws/install/setup.bash
.venv/bin/python scripts/calibrate_tactile_bend.py --side left
.venv/bin/python scripts/calibrate_tactile_bend.py --side right
```

采集完成后重启服务即可。

### 8.2 手部姿态

- `solve_state[0..15]`：依次为食指、中指、无名指、小拇指；每指四项均为 `[MCP 屈曲, MCP 侧摆, PIP 屈曲, DIP 屈曲]`。
- `solve_state[16..18]`：拇指 MCP 屈曲、侧摆和 IP 屈曲。
- `solve_state[19..22]`：拇指 CMC 四元数，顺序 `w,x,y,z`。
- `solve_state[23..26]`：手背四元数，顺序 `w,x,y,z`。
- 指根位置来自 `mcp_offsets_mm`，姿态校正不会移动指根。
- 左右手分别使用各自的 `solve_state`，不会互相同步。
- 左手四指 MCP 侧摆可通过 `left_mcp_swing_offsets_deg` 校正零位，并通过 `left_mcp_swing_limits_deg` 限制进入 FK 的有效角；角度面板仍显示原始值。

如果只有某一只手卡顿，先检查 `/hand_frame` 中对应 `solve_state_left/right` 是否连续变化。若延迟始终跟随同一根线缆或采集通道，优先排查设备、线缆和上游解算，而不是网页渲染。

如果某根手指长期卡在侧摆边界，先检查其原始角是否长期超出限位。不要直接把带有固定零位偏置的原始角限制在以 `0°` 为中心的狭小范围；需要先配置该手指的零位偏置，再限制相对活动范围。

## 9. 常用诊断

### 9.1 一键诊断

```bash
./scripts/diagnose.sh
```

该脚本检查 Python/ROS 导入、Topic、端口和后端进程。

### 9.2 后端健康状态

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/status
```

### 9.3 没有画面时

依次确认：

1. `ping <设备IP>` 是否成功。
2. `nc -vz <设备IP> 7447` 是否成功。
3. 诊断终端是否设置了 `RMW_IMPLEMENTATION=rmw_zenoh_cpp`。
4. `ZENOH_CONFIG_OVERRIDE` endpoint 是否为设备当前 IP。
5. Topic 名称和类型是否与 `config/config.yaml` 完全一致。
6. `source /opt/ros/jazzy/setup.bash` 和 `source hand_msg_ws/install/setup.bash` 是否成功。
7. `/api/status` 中 `ros.error` 是否有错误。
8. RGB Topic 是否真的在发布，而不只是能被发现。

### 9.4 端口被占用

```bash
ss -ltnp | grep ':8000'
ps -ef | grep '[b]ackend.main'
```

换端口启动：

```bash
EGO_LOONG_LIVE_PORT=8001 ./scripts/run.sh
```

### 9.5 自定义消息导入失败

```bash
rm -rf hand_msg_ws/build hand_msg_ws/install hand_msg_ws/log
source /opt/ros/jazzy/setup.bash
cd hand_msg_ws
colcon build --symlink-install --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
cd ..
source hand_msg_ws/install/setup.bash
/usr/bin/python3 -c 'from hand_frame.msg import HandFrame; print(HandFrame)'
```

## 10. 开机自动启动（可选）

确认手动启动完全正常后，再配置 systemd。创建：

```bash
sudo nano /etc/systemd/system/ego-loong-live.service
```

示例内容：

```ini
[Unit]
Description=Ego-Loong Live Visualization
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<用户名>
WorkingDirectory=/home/<用户名>/Ego-Loong-Live
Environment=EGO_ZENOH_ROUTER_ENDPOINT=tcp/192.168.3.13:7447
ExecStart=/home/<用户名>/Ego-Loong-Live/scripts/run.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ego-loong-live.service
systemctl status ego-loong-live.service
journalctl -u ego-loong-live.service -f
```

多实例应分别创建 `ego-loong-device01.service`、`ego-loong-device02.service`，并设置不同配置、endpoint 和端口。

## 11. 测试

```bash
cd ~/Ego-Loong-Live
.venv/bin/python -m unittest discover -s tests -v
```

测试覆盖：

- 配置约束
- 68 点触觉映射
- 手部关节与骨架映射
- 手部表面结构
- WebSocket 有界队列

## 12. 仓库结构

```text
backend/                          FastAPI、ROS 订阅和数据处理
backend/tactile_bend_decoupler.py 触觉弯曲姿态模板匹配与解耦
config/config.yaml                默认运行配置
config/tactile/                   左右手触觉弯曲解耦标定文件
config/retarget_hand_config.reference.json
                                  手型骨长、指根和姿态校正
frontend/                         页面、样式、Canvas、Three.js
frontend/vendor/                  本地 Three.js 依赖
hand_msg_ws/src/hand_frame/       自定义 ROS 2 消息源码
scripts/install.sh                创建虚拟环境并编译消息
scripts/run.sh                    真实 ROS 2/Zenoh 模式
scripts/run_mock.sh               Mock 模式
scripts/check_topics.sh           Topic 发现、类型和频率检查
scripts/diagnose.sh               环境、Topic、端口和进程诊断
scripts/calibrate_tactile_bend.py 左右手空载弯曲模板采集
tests/                            单元测试
docs/interface_audit.md           数据接口审计记录
```

## 13. 当前限制

- 一个后端实例只处理一套设备。
- 当前没有在一个网页内动态切换四套设备的功能。
- 项目不包含相机驱动、手套采集节点或 Zenoh Router 启动服务。
- 页面采集控制接口是安全占位，不会启动或停止外部采集程序。
- `HandFrame` 没有设备 ID，多设备必须通过 Topic 命名空间、ROS Domain 或隔离的 Zenoh 会话区分。
- 触觉消息尚未定义物理单位，页面显示原始值相对空载基线的 Delta。
- 手部显示是基于 `solve_state[27]` 的程序化重建，不是 MANO 蒙皮模型。

## 14. 新电脑迁移验收清单

- [ ] Ubuntu 24.04、ROS 2 Jazzy、`rmw_zenoh_cpp` 安装完成
- [ ] 仓库只复制源码，没有复用旧 `.venv/build/install/log`
- [ ] `./scripts/install.sh` 无错误完成
- [ ] `HandFrame` 可被 `/usr/bin/python3` 和 `.venv/bin/python` 导入
- [ ] Mock 页面 RGB、触觉、手部姿态显示正常
- [ ] 浏览器 WebGL 和硬件加速正常
- [ ] 笔记本能 ping 通设备，7447/TCP 可连接
- [ ] 使用与正式服务相同的 Zenoh 配置可发现两个默认 Topic
- [ ] 真实 RGB、双手触觉和双手姿态连续显示
- [ ] 左右手弯曲标定文件均存在，启动前 24 帧保持空载
- [ ] 左右手数据没有串线，右手拇指位于手掌左侧
- [ ] 双实例端口、配置和设备来源相互独立
- [ ] 大屏设置为扩展模式而非镜像模式
- [ ] 满负载连续测试至少 1 小时，无持续增加的延迟或内存占用
