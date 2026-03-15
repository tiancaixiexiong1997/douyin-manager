#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${REPO_URL:-}"
APP_DIR="${APP_DIR:-/opt/douyin-manager}"
GIT_BRANCH="${GIT_BRANCH:-main}"
APP_DOMAIN="${APP_DOMAIN:-}"
ENABLE_PROD_PROFILE="${ENABLE_PROD_PROFILE:-auto}"
DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-admin123456}"
APP_TIMEZONE="${APP_TIMEZONE:-Asia/Shanghai}"

log() {
  printf '\033[1;34m[install]\033[0m %s\n' "$1"
}

warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$1"
}

die() {
  printf '\033[1;31m[error]\033[0m %s\n' "$1" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "请使用 root 或 sudo 运行此脚本"
  fi
}

detect_pm() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "apt"
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    echo "dnf"
    return
  fi
  if command -v yum >/dev/null 2>&1; then
    echo "yum"
    return
  fi
  die "未识别的系统包管理器，仅支持 apt/dnf/yum"
}

install_base_packages() {
  local pm="$1"
  case "$pm" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y
      apt-get install -y ca-certificates curl git openssl
      ;;
    dnf)
      dnf install -y ca-certificates curl git openssl
      ;;
    yum)
      yum install -y ca-certificates curl git openssl
      ;;
  esac
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker 和 Docker Compose 已安装，跳过"
    return
  fi

  log "安装 Docker"
  curl -fsSL https://get.docker.com | sh

  if ! command -v docker >/dev/null 2>&1; then
    die "Docker 安装失败"
  fi
}

ensure_docker_started() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable docker >/dev/null 2>&1 || true
    systemctl restart docker
  else
    service docker restart || true
  fi
}

clone_or_update_repo() {
  [[ -n "${REPO_URL}" ]] || die "请先提供 REPO_URL，例如 REPO_URL=git@github.com:you/douyin-manager.git"

  mkdir -p "$(dirname "${APP_DIR}")"
  if [[ ! -d "${APP_DIR}/.git" ]]; then
    log "克隆项目到 ${APP_DIR}"
    git clone --branch "${GIT_BRANCH}" "${REPO_URL}" "${APP_DIR}"
    return
  fi

  log "检测到已有仓库，更新到最新 ${GIT_BRANCH}"
  git -C "${APP_DIR}" fetch origin
  git -C "${APP_DIR}" checkout "${GIT_BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${GIT_BRANCH}"
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"

  if grep -q "^${key}=" "${file}"; then
    sed -i.bak "s#^${key}=.*#${key}=${value}#" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

get_env_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "^${key}=" "${file}" | tail -n 1 || true)"
  printf '%s' "${line#*=}"
}

prepare_env_file() {
  local env_file="${APP_DIR}/.env"
  local env_example="${APP_DIR}/.env.example"

  [[ -f "${env_example}" ]] || die "未找到 ${env_example}"

  if [[ ! -f "${env_file}" ]]; then
    log "创建 .env"
    cp "${env_example}" "${env_file}"
  else
    log "检测到现有 .env，保留原文件并仅补充必要项"
  fi

  local current_secret_key
  current_secret_key="$(get_env_value "${env_file}" "AUTH_SECRET_KEY")"

  if [[ -z "${current_secret_key}" || "${current_secret_key}" == "replace-with-a-strong-random-secret" || "${current_secret_key}" == "change-me-in-production" ]]; then
    current_secret_key="$(openssl rand -hex 32)"
  fi

  set_env_value "${env_file}" "APP_TIMEZONE" "${APP_TIMEZONE}"
  set_env_value "${env_file}" "DEFAULT_ADMIN_USERNAME" "${DEFAULT_ADMIN_USERNAME}"
  set_env_value "${env_file}" "DEFAULT_ADMIN_PASSWORD" "${DEFAULT_ADMIN_PASSWORD}"
  set_env_value "${env_file}" "AUTH_SECRET_KEY" "${current_secret_key}"
  set_env_value "${env_file}" "APP_DOMAIN" "${APP_DOMAIN}"
  set_env_value "${env_file}" "BACKEND_PORT_BIND" "127.0.0.1:8000:8000"

  if [[ -n "${APP_DOMAIN}" ]]; then
    set_env_value "${env_file}" "COOKIE_SECURE" "true"
    set_env_value "${env_file}" "COOKIE_SAMESITE" "lax"
  else
    set_env_value "${env_file}" "COOKIE_SECURE" "false"
    set_env_value "${env_file}" "COOKIE_SAMESITE" "lax"
  fi

  if ! grep -q "^AI_API_KEY=" "${env_file}"; then
    printf 'AI_API_KEY=\n' >> "${env_file}"
  fi
  if ! grep -q "^AI_API_KEY_BACKUP=" "${env_file}"; then
    printf 'AI_API_KEY_BACKUP=\n' >> "${env_file}"
  fi
  if ! grep -q "^DOUYIN_COOKIE=" "${env_file}"; then
    printf 'DOUYIN_COOKIE=\n' >> "${env_file}"
  fi
}

ensure_directories() {
  mkdir -p "${APP_DIR}/data" "${APP_DIR}/logs" "${APP_DIR}/config/caddy"
}

compose_up() {
  local profile_flag=""

  case "${ENABLE_PROD_PROFILE}" in
    true)
      profile_flag="--profile prod"
      ;;
    false)
      profile_flag=""
      ;;
    auto)
      if [[ -n "${APP_DOMAIN}" ]]; then
        profile_flag="--profile prod"
      fi
      ;;
    *)
      die "ENABLE_PROD_PROFILE 只支持 true/false/auto"
      ;;
  esac

  log "启动容器"
  (
    cd "${APP_DIR}"
    docker compose ${profile_flag} up -d --build
  )
}

print_summary() {
  cat <<EOF

部署完成。

项目目录: ${APP_DIR}
域名: ${APP_DOMAIN:-未设置（当前为本地端口模式）}
管理员账号: ${DEFAULT_ADMIN_USERNAME}
管理员密码: ${DEFAULT_ADMIN_PASSWORD}

接下来建议你做这几步：
1. 打开站点
   - 未设置域名时: http://服务器IP:3000
   - 设置了域名且启用 prod 时: https://${APP_DOMAIN}
2. 登录后台后，到“设置 -> 基础配置”填写 AI_API_KEY
3. 到“设置 -> 爬虫与认证”填写 Douyin Cookie，或使用 Cookie 提取助手

常用排查命令：
cd ${APP_DIR}
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend

EOF
}

main() {
  require_root
  local pm
  pm="$(detect_pm)"
  install_base_packages "${pm}"
  install_docker
  ensure_docker_started
  clone_or_update_repo
  prepare_env_file
  ensure_directories
  compose_up
  print_summary
}

main "$@"
