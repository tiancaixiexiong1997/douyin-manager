# UI Design System (Frontend)

本文件用于锁定当前站点的统一视觉和交互规范，避免后续多人开发造成风格漂移。

## 1. 基础原则

- 一致性优先：同一语义的组件必须使用同一视觉规则。
- 信息密度可控：先保证层级清晰，再追求视觉装饰。
- 浅色干净、深色有层次：浅色主题避免灰脏叠层，深色主题避免纯黑糊块。
- 动效服务信息：动效只用于状态变化和焦点引导，不做无意义炫技。

## 2. 全局 Token 来源

全局设计令牌统一定义在：
- `src/index.css`

重点 token：
- 颜色：`--bg-*` `--text-*` `--border-*` `--primary-*` `--accent-*`
- 圆角：`--radius-sm/md/lg/xl`
- 间距：`--space-*` + `--page-padding-x` `--page-padding-x-mobile`
- 字号层级：`--font-display` `--font-title-1/2/3` `--font-body` `--font-caption`
- 控件高度：`--control-height` `--control-height-sm` `--control-height-lg`
- 动效：`--transition-*` `--ease-*` `--motion-enter*`

禁止在业务页面重复发明以上 token。

## 3. 组件规范

### 3.1 按钮（`.btn`）

- 使用统一高度，不手写零散 padding 高度。
- 主按钮：`btn btn-primary`
- 次按钮：`btn btn-ghost`
- 危险按钮：`btn btn-danger`
- 图标按钮：`btn btn-icon`
- 小号：`btn-sm`，大号：`btn-lg`

### 3.2 输入与文本域（`.form-input`）

- 输入框统一使用 `.form-input`。
- 文本域统一叠加 `.form-textarea`。
- 焦点态必须保留（不可移除 focus ring）。

### 3.3 卡片（`.card`）

- 页面信息块优先使用 `.card`。
- 需要强调 hover 时使用 `.card-glow`。
- 避免业务页重复定义截然不同的卡片边框和阴影。

### 3.4 标签（`.badge`）

- 状态标签统一用：`.badge-*`（`purple/green/yellow/red/blue`）。
- 不再新建自定义小胶囊样式，除非语义不同且复用价值高。

### 3.5 弹窗（`.modal`）

- 遮罩/容器/标题/页脚统一用：`.modal-overlay` `.modal` `.modal-title` `.modal-footer`。
- 业务弹窗只扩展尺寸和局部结构，不重写整体视觉体系。

## 4. 页面布局节奏

- 主内容容器统一由 `App.css` 的 `.main-content` 控制外边距和内边距。
- 页面推荐结构：
  1. Hero 区（页面定位 + 主操作）
  2. Overview 区（关键指标）
  3. List/Content 区（核心业务）
- 区块间距优先使用 `--space-*`，避免随处写随机 `margin`。

## 5. 主题规范

### 5.1 深色主题

- 允许渐变和轻玻璃感，但保留边框层级。
- 卡片和面板避免大面积纯黑，保持可分层。

### 5.2 浅色主题

- 优先白底 + 浅边框 + 轻阴影。
- 避免深色半透明叠层直接复用到浅色主题。
- 若页面有特殊深色视觉，必须提供 `[data-theme='light']` 覆盖。

## 6. 动效规范

- 入场统一使用 `animate-fade-in` / `animate-scale-in`。
- 交互过渡优先使用 token：`--transition-fast/normal/slow`。
- 避免 `transition: all`，改为精确属性。
- 保持 `prefers-reduced-motion` 兼容。

## 7. 新页面开发检查清单

- 是否只使用全局 token，而非硬编码色值/圆角/阴影？
- 是否复用 `.btn` `.form-input` `.card` `.badge` `.modal`？
- 浅色主题是否单独检查并去除“发灰发脏”？
- 移动端（<=768px）是否有明确布局策略？
- 是否通过 `npm run lint` 和 `npm run build`？

## 8. 现有页面状态（2026-03）

已统一：
- 登录页（全局门禁）
- 看板
- 博主 IP 库
- 账号策划
- 项目详情
- 脚本拆解复刻
- 无水印下载
- 系统设置

后续新增页面请遵循本文件，不再引入新的视觉体系。
