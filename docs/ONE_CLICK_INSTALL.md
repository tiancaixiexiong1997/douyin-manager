# 一键安装脚本说明

这个项目现在提供了一个不携带任何私密信息的一键部署脚本：

- [scripts/install_vps.sh](/Users/xiexiong/Desktop/douyin/douyin-manager/scripts/install_vps.sh)

它的设计目标是：

- 新 VPS 上自动安装 Docker
- 自动拉取 Git 仓库代码
- 自动生成 `.env`
- 默认不写入 `AI_API_KEY`
- 默认不写入 `DOUYIN_COOKIE`
- 启动 Docker Compose

## 适用前提

推荐你先把代码上传到 GitHub 私有仓库，然后再在新 VPS 上执行脚本。

原因是脚本默认通过 `git clone` 获取代码，这样最稳定，也最适合以后更新版本。

## 第一次使用前要做什么

1. 把当前项目上传到 GitHub 私有仓库
2. 确保 VPS 能访问 GitHub
3. 在 VPS 上准备好 root 或 sudo 权限

## 使用方式

先给脚本可执行权限：

```bash
chmod +x scripts/install_vps.sh
```

### 方式一：项目已经在服务器上

```bash
sudo REPO_URL=git@github.com:yourname/douyin-manager.git \
APP_DOMAIN=your-domain.com \
bash scripts/install_vps.sh
```

### 方式二：未来做成远程一键安装

当这个脚本已经在 GitHub 仓库里后，新 VPS 可以这样执行：

```bash
curl -fsSL https://raw.githubusercontent.com/yourname/douyin-manager/main/scripts/install_vps.sh -o /tmp/install_vps.sh
chmod +x /tmp/install_vps.sh
sudo REPO_URL=git@github.com:yourname/douyin-manager.git APP_DOMAIN=your-domain.com /tmp/install_vps.sh
```

## 重要环境变量

- `REPO_URL`
  - 必填，Git 仓库地址
- `APP_DIR`
  - 可选，默认 `/opt/douyin-manager`
- `GIT_BRANCH`
  - 可选，默认 `main`
- `APP_DOMAIN`
  - 可选，填了会自动启用 `prod` profile
- `ENABLE_PROD_PROFILE`
  - 可选：`true` / `false` / `auto`
  - 默认 `auto`
- `DEFAULT_ADMIN_USERNAME`
  - 可选，默认 `admin`
- `DEFAULT_ADMIN_PASSWORD`
  - 可选，默认 `admin123456`

## 脚本不会做的事

为了避免泄露敏感信息，这个脚本不会内置：

- `AI_API_KEY`
- `AI_API_KEY_BACKUP`
- `DOUYIN_COOKIE`

这些需要你在系统启动后，到后台设置页手动填写。

## 启动后检查

```bash
cd /opt/douyin-manager
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

如果设置了域名并启用了 `prod` profile，访问：

```text
https://your-domain.com
```

如果没有设置域名，访问：

```text
http://服务器IP:3000
```
