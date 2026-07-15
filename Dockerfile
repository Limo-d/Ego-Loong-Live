# syntax=docker/dockerfile:1

# Official ROS image based on Ubuntu 24.04 (Noble).
FROM ros:jazzy-ros-base-noble

ARG DEBIAN_FRONTEND=noninteractive
ARG APP_USER=ego
ARG APP_UID=10001
ARG APP_GID=10001
ARG UBUNTU_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu
ARG UBUNTU_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu
ARG ROS_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu
ARG PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/ego-venv \
    PATH=/opt/ego-venv/bin:${PATH} \
    APP_ROOT=/opt/ego-loong-live \
    RMW_IMPLEMENTATION=rmw_zenoh_cpp \
    EGO_ZENOH_ROUTER_ENDPOINT=tcp/192.168.3.13:7447

SHELL ["/bin/bash", "-c"]

RUN sed -i \
      -e "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_MIRROR}|g" \
      -e "s|http://security.ubuntu.com/ubuntu|${UBUNTU_SECURITY_MIRROR}|g" \
      /etc/apt/sources.list.d/ubuntu.sources \
    && sed -i \
      -e "s|http://packages.ros.org/ros2/ubuntu|${ROS_MIRROR}|g" \
      -e "s|Types: deb deb-src|Types: deb|g" \
      /usr/share/ros-apt-source/ros2.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-rmw-zenoh-cpp \
      ros-jazzy-rclpy \
      ros-jazzy-sensor-msgs \
      ros-jazzy-rosidl-default-generators \
      ros-jazzy-rosidl-default-runtime \
      python3-colcon-common-extensions \
      python3-numpy \
      python3-pil \
      python3-pip \
      python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_ROOT}

# Install web dependencies in a virtual environment that can also see the
# Ubuntu/ROS Python packages (rclpy, Pillow and NumPy).
COPY requirements.txt pyproject.toml ./
RUN python3 -m venv --system-site-packages ${VIRTUAL_ENV} \
    && ${VIRTUAL_ENV}/bin/python -m pip install \
         --no-cache-dir --timeout 120 --retries 8 \
         --index-url ${PYPI_MIRROR} \
         -r requirements.txt

# Build the project-local ROS 2 interface before copying the rest of the source
# so ordinary frontend/backend edits can reuse this Docker layer.
COPY hand_msg_ws/src/ ./hand_msg_ws/src/
RUN source /opt/ros/jazzy/setup.bash \
    && cd hand_msg_ws \
    && colcon build --merge-install \
         --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3 \
    && rm -rf build log \
    && source install/setup.bash \
    && ${VIRTUAL_ENV}/bin/python -c 'import rclpy; from hand_frame.msg import HandFrame; print("ROS 2 + hand_frame: OK")'

COPY backend/ ./backend/
COPY config/ ./config/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/
COPY docker/entrypoint.sh /usr/local/bin/ego-loong-entrypoint

RUN chmod +x /usr/local/bin/ego-loong-entrypoint scripts/*.sh \
    && groupadd --gid ${APP_GID} ${APP_USER} \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /bin/bash ${APP_USER} \
    && chown -R ${APP_UID}:${APP_GID} ${APP_ROOT} ${VIRTUAL_ENV}

USER ${APP_USER}

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).read()" || exit 1

ENTRYPOINT ["/usr/local/bin/ego-loong-entrypoint"]
CMD ["python", "-m", "backend.main"]
