#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${REPO_URL:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
APP_DIR="${APP_DIR:-/opt/douyin-manager}"
GIT_BRANCH="${GIT_BRANCH:-main}"
APP_DOMAIN="${APP_DOMAIN:-}"
ENABLE_PROD_PROFILE="${ENABLE_PROD_PROFILE:-auto}"
DEFAULT_ADMIN_USERNAME="${DEFAULT_ADMIN_USERNAME:-admin}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-admin123456}"
APP_TIMEZONE="${APP_TIMEZONE:-Asia/Shanghai}"
INTERACTIVE_MODE="${INTERACTIVE_MODE:-auto}"
REPO_VISIBILITY="${REPO_VISIBILITY:-}"
INSTALL_MODE_LABEL=""
DEPLOY_ACCESS_URL=""
PROFILE_DESCRIPTION=""
COLOR_RESET=$'\033[0m'
COLOR_BLUE=$'\033[1;34m'
COLOR_CYAN=$'\033[1;36m'
COLOR_GREEN=$'\033[1;32m'
COLOR_YELLOW=$'\033[1;33m'
COLOR_MAGENTA=$'\033[1;35m'
export PAGER=cat
export SYSTEMD_PAGER=cat
export GIT_PAGER=cat

log() {
  printf '%s[install]%s %s\n' "${COLOR_BLUE}" "${COLOR_RESET}" "$1"
}

warn() {
  printf '%s[warn]%s %s\n' "${COLOR_YELLOW}" "${COLOR_RESET}" "$1"
}

die() {
  printf '\033[1;31m[error]%s %s\n' "${COLOR_RESET}" "$1" >&2
  exit 1
}

print_box() {
  local color="$1"
  local title="$2"
  shift 2
  local lines=("$@")

  if ! has_tty; then
    printf '%s\n' "${title}"
    printf '%s\n' "${lines[@]}"
    return
  fi

  printf '%s============================================================%s\n' "${color}" "${COLOR_RESET}" > /dev/tty
  printf '%s  %s%s\n' "${color}" "${title}" "${COLOR_RESET}" > /dev/tty
  printf '%s============================================================%s\n' "${color}" "${COLOR_RESET}" > /dev/tty
  local line
  for line in "${lines[@]}"; do
    printf '  %s\n' "${line}" > /dev/tty
  done
  printf '%s============================================================%s\n\n' "${color}" "${COLOR_RESET}" > /dev/tty
}

print_banner() {
  if ! has_tty; then
    return
  fi

  print_box "${COLOR_MAGENTA}" "Douyin Manager 一键安装向导" \
    "这个安装器会帮助你在全新 VPS 上完成：" \
    "1. Docker 安装" \
    "2. 项目代码拉取" \
    "3. .env 自动生成" \
    "4. 容器启动与初始化"
}

print_step() {
  local step="$1"
  local title="$2"
  printf '\n%s[%s/6]%s %s\n' "${COLOR_CYAN}" "${step}" "${COLOR_RESET}" "${title}"
}

print_success_panel() {
  if has_tty; then
    print_box "${COLOR_GREEN}" "安装完成" \
      "安装模式   : ${INSTALL_MODE_LABEL}" \
      "项目目录   : ${APP_DIR}" \
      "访问地址   : ${DEPLOY_ACCESS_URL}" \
      "启动模式   : ${PROFILE_DESCRIPTION}" \
      "" \
      "默认管理员账号" \
      "用户名     : ${DEFAULT_ADMIN_USERNAME}" \
      "密码       : ${DEFAULT_ADMIN_PASSWORD}" \
      "" \
      "安装后建议" \
      "1. 立即登录后台并修改管理员密码" \
      "2. 到“设置 -> 基础配置”填写 AI_API_KEY" \
      "3. 到“设置 -> 爬虫与认证”填写 Douyin Cookie" \
      "" \
      "常用排查命令" \
      "cd ${APP_DIR}" \
      "docker compose ps" \
      "docker compose logs -f backend" \
      "docker compose logs -f frontend"
    return
  fi

  cat <<EOF
安装完成
安装模式   : ${INSTALL_MODE_LABEL}
项目目录   : ${APP_DIR}
访问地址   : ${DEPLOY_ACCESS_URL}
启动模式   : ${PROFILE_DESCRIPTION}
用户名     : ${DEFAULT_ADMIN_USERNAME}
密码       : ${DEFAULT_ADMIN_PASSWORD}
EOF
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "请使用 root 或 sudo 运行此脚本"
  fi
}

has_tty() {
  [[ -r /dev/tty && -w /dev/tty ]]
}

prompt_input() {
  local message="$1"
  local default_value="${2:-}"
  local answer=""

  if ! has_tty; then
    printf '%s' "${default_value}"
    return
  fi

  if [[ -n "${default_value}" ]]; then
    printf "%s [%s]: " "${message}" "${default_value}" > /dev/tty
  else
    printf "%s: " "${message}" > /dev/tty
  fi
  IFS= read -r answer < /dev/tty || true
  if [[ -z "${answer}" ]]; then
    answer="${default_value}"
  fi
  printf '%s' "${answer}"
}

prompt_secret() {
  local message="$1"
  local answer=""

  if ! has_tty; then
    printf ''
    return
  fi

  printf "%s: " "${message}" > /dev/tty
  stty -echo < /dev/tty
  IFS= read -r answer < /dev/tty || true
  stty echo < /dev/tty
  printf '\n' > /dev/tty
  printf '%s' "${answer}"
}

prompt_choice() {
  local message="$1"
  shift
  local options=("$@")
  local index=1
  local choice=""

  if ! has_tty; then
    printf '%s' "${options[0]}"
    return
  fi

  printf "%s\n" "${message}" > /dev/tty
  for option in "${options[@]}"; do
    printf "  %s) %s\n" "${index}" "${option}" > /dev/tty
    index=$((index + 1))
  done

  while true; do
    printf "请选择 [1-%s]: " "${#options[@]}" > /dev/tty
    IFS= read -r choice < /dev/tty || true
    if [[ "${choice}" =~ ^[1-9][0-9]*$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
      printf '%s' "${options[choice-1]}"
      return
    fi
    printf "输入无效，请重试。\n" > /dev/tty
  done
}

interactive_setup() {
  local use_interactive="${INTERACTIVE_MODE}"

  if [[ "${use_interactive}" == "auto" ]]; then
    if has_tty; then
      use_interactive="true"
    else
      use_interactive="false"
    fi
  fi

  if [[ "${use_interactive}" != "true" ]]; then
    return
  fi

  print_banner
  print_step 1 "收集安装信息"
  log "进入交互式安装向导"

  if [[ -z "${GITHUB_REPO}" && -z "${REPO_URL}" ]]; then
    GITHUB_REPO="$(prompt_input "GitHub 仓库（格式：用户名/仓库名）" "tiancaixiexiong1997/douyin-manager")"
  fi

  if [[ -z "${REPO_VISIBILITY}" ]]; then
    local repo_visibility_choice
    repo_visibility_choice="$(prompt_choice "请选择仓库类型" "私有仓库（需要 GitHub Token）" "公共仓库")"
    if [[ "${repo_visibility_choice}" == "私有仓库（需要 GitHub Token）" ]]; then
      REPO_VISIBILITY="private"
      INSTALL_MODE_LABEL="私有仓库安装"
    else
      REPO_VISIBILITY="public"
      INSTALL_MODE_LABEL="公共仓库安装"
    fi
  fi

  if [[ "${REPO_VISIBILITY}" == "private" && -z "${GITHUB_TOKEN}" && -z "${REPO_URL}" ]]; then
    GITHUB_TOKEN="$(prompt_secret "请输入 GitHub Token（私有仓库需要）")"
  fi

  if [[ -z "${APP_DOMAIN}" ]]; then
    APP_DOMAIN="$(prompt_input "绑定域名（留空则按 IP:3000 启动）")"
  fi

  if [[ -z "${ENABLE_PROD_PROFILE}" || "${ENABLE_PROD_PROFILE}" == "auto" ]]; then
    if [[ -n "${APP_DOMAIN}" ]]; then
      ENABLE_PROD_PROFILE="true"
    else
      local deploy_mode_choice
      deploy_mode_choice="$(prompt_choice "请选择部署模式" "仅本地端口模式（IP:3000）" "生产模式（域名 + HTTPS）")"
      if [[ "${deploy_mode_choice}" == "生产模式（域名 + HTTPS）" ]]; then
        ENABLE_PROD_PROFILE="true"
      else
        ENABLE_PROD_PROFILE="false"
      fi
    fi
  fi

  DEFAULT_ADMIN_USERNAME="$(prompt_input "管理员账号" "${DEFAULT_ADMIN_USERNAME}")"
  DEFAULT_ADMIN_PASSWORD="$(prompt_input "管理员密码" "${DEFAULT_ADMIN_PASSWORD}")"
  APP_DIR="$(prompt_input "安装目录" "${APP_DIR}")"
  GIT_BRANCH="$(prompt_input "Git 分支" "${GIT_BRANCH}")"
  APP_TIMEZONE="$(prompt_input "时区" "${APP_TIMEZONE}")"
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
  print_step 2 "安装基础依赖"
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
  print_step 3 "安装 Docker 环境"
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
  print_step 4 "拉取项目代码"
  local resolved_repo_url="${REPO_URL}"

  if [[ -z "${resolved_repo_url}" && -n "${GITHUB_REPO}" ]]; then
    if [[ -n "${GITHUB_TOKEN}" ]]; then
      resolved_repo_url="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git"
    else
      resolved_repo_url="https://github.com/${GITHUB_REPO}.git"
    fi
  fi

  [[ -n "${resolved_repo_url}" ]] || die "请先提供 REPO_URL，或提供 GITHUB_REPO（例如 tiancaixiexiong1997/douyin-manager）"

  mkdir -p "$(dirname "${APP_DIR}")"
  if [[ ! -d "${APP_DIR}/.git" ]]; then
    log "克隆项目到 ${APP_DIR}"
    git clone --branch "${GIT_BRANCH}" "${resolved_repo_url}" "${APP_DIR}"
    return
  fi

  log "检测到已有仓库，更新到最新 ${GIT_BRANCH}"
  git -C "${APP_DIR}" remote set-url origin "${resolved_repo_url}" || true
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
  print_step 5 "生成部署配置"
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
  print_step 6 "启动项目容器"
  local profile_flag=""

  case "${ENABLE_PROD_PROFILE}" in
    true)
      profile_flag="--profile prod"
      PROFILE_DESCRIPTION="生产模式（域名 + HTTPS）"
      ;;
    false)
      profile_flag=""
      PROFILE_DESCRIPTION="本地端口模式（IP:3000）"
      ;;
    auto)
      if [[ -n "${APP_DOMAIN}" ]]; then
        profile_flag="--profile prod"
        PROFILE_DESCRIPTION="生产模式（域名 + HTTPS）"
      else
        PROFILE_DESCRIPTION="本地端口模式（IP:3000）"
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

  if [[ -n "${APP_DOMAIN}" && "${PROFILE_DESCRIPTION}" == "生产模式（域名 + HTTPS）" ]]; then
    DEPLOY_ACCESS_URL="https://${APP_DOMAIN}"
  else
    DEPLOY_ACCESS_URL="http://服务器IP:3000"
  fi
}

print_summary() {
  print_success_panel
}

main() {
  interactive_setup
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
