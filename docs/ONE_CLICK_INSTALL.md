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

推荐你先把代码上传到 GitHub 仓库，然后再在新 VPS 上执行脚本。

原因是脚本默认通过 `git clone` 获取代码，这样最稳定，也最适合以后更新版本。

## 第一次使用前要做什么

1. 把当前项目上传到 GitHub 仓库
2. 确保 VPS 能访问 GitHub
3. 在 VPS 上准备好 root 或 sudo 权限

## 使用方式

先给脚本可执行权限：

```bash
chmod +x scripts/install_vps.sh
```

## 像宝塔那样的交互式安装

脚本现在支持交互式向导。

也就是说，你在新 VPS 上执行命令后，它会继续一步步询问：

- 欢迎页说明
- 仓库地址
- 仓库是否私有
- 域名
- 是否启用生产模式
- 管理员账号
- 管理员密码
- 安装目录
- Git 分支
- 时区

同时还会显示：

- `1/6` 到 `6/6` 的安装进度
- 彩色分隔框与区块标题
- 更清晰的编号菜单
- 安装完成后的访问地址和默认账号密码区块
- 默认关闭 `systemctl/git` 分页，避免卡在 `lines 1-23` 之类的界面
- 安装结束后再次单独打印访问入口和默认账号密码

### 私有仓库推荐用法

这是最接近“宝塔面板安装命令”的方式：

```bash
read -s -p "GitHub Token: " GITHUB_TOKEN; echo
curl -fsSL -H "Authorization: Bearer ${GITHUB_TOKEN}" \
https://raw.githubusercontent.com/tiancaixiexiong1997/douyin-manager/main/scripts/install_vps.sh | \
sudo INTERACTIVE_MODE=true GITHUB_TOKEN="${GITHUB_TOKEN}" bash
unset GITHUB_TOKEN
```

执行后，脚本会继续在终端里弹出交互问题。

### 公网仓库推荐用法

如果仓库是公开的，可以直接：

```bash
curl -fsSL https://raw.githubusercontent.com/yourname/douyin-manager/main/scripts/install_vps.sh | \
sudo INTERACTIVE_MODE=true bash
```

### 方式一：项目已经在服务器上

```bash
sudo REPO_URL=git@github.com:yourname/douyin-manager.git \
APP_DOMAIN=your-domain.com \
bash scripts/install_vps.sh
```

### 方式二：公网仓库一条命令安装

如果你的仓库是公开的，新 VPS 可以直接执行：

```bash
curl -fsSL https://raw.githubusercontent.com/yourname/douyin-manager/main/scripts/install_vps.sh | \
sudo GITHUB_REPO=yourname/douyin-manager APP_DOMAIN=your-domain.com bash
```

### 方式三：私有仓库一条命令安装

如果你的仓库是私有的，需要准备一个 GitHub Personal Access Token。

然后在新 VPS 上执行：

```bash
curl -fsSL -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
https://raw.githubusercontent.com/yourname/douyin-manager/main/scripts/install_vps.sh | \
sudo GITHUB_REPO=yourname/douyin-manager GITHUB_TOKEN=YOUR_GITHUB_TOKEN APP_DOMAIN=your-domain.com bash
```

这条命令会：

- 先从 GitHub 拉取安装脚本
- 再用 `GITHUB_TOKEN` 克隆私有仓库
- 自动生成 `.env`
- 启动容器

## 重要环境变量

- `REPO_URL`
  - 可选，直接指定完整 Git 仓库地址
- `GITHUB_REPO`
  - 可选，格式如 `tiancaixiexiong1997/douyin-manager`
- `GITHUB_TOKEN`
  - 可选，私有仓库克隆时使用；公网仓库可不填
- `APP_DIR`
  - 可选，默认 `/opt/douyin-manager`
- `GIT_BRANCH`
  - 可选，默认 `main`
- `APP_DOMAIN`
  - 可选，填了会自动启用 `prod` profile
- `FRONTEND_PORT_BIND`
  - 通常不需要手动填
  - IP 模式会自动设为 `3000:80`
  - 域名模式会自动设为 `127.0.0.1:3000:80`
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

## 当前项目可直接套用

如果你继续保持当前仓库为私有仓库，未来新 VPS 可直接使用这条命令：

```bash
read -s -p "GitHub Token: " GITHUB_TOKEN; echo
curl -fsSL -H "Authorization: Bearer ${GITHUB_TOKEN}" \
https://raw.githubusercontent.com/tiancaixiexiong1997/douyin-manager/main/scripts/install_vps.sh | \
sudo INTERACTIVE_MODE=true GITHUB_TOKEN="${GITHUB_TOKEN}" bash
unset GITHUB_TOKEN
```

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
