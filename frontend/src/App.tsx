import { BrowserRouter as Router, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import { LogOut } from 'lucide-react';

import { authApi, type CurrentUserResponse } from './api/client';
import { AnimatedLoginPage } from './components/auth/AnimatedLoginPage';
import { GlobalToaster } from './components/GlobalToaster';
import './index.css';
import './App.css';
import {
  LayoutDashboard, Calendar, Users, Sparkles, ChevronRight, RefreshCw, SettingsIcon, Download, Sun, Moon, AppLogo, Clock
} from './components/Icons';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';

const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'));
const TaskCenter = lazy(() => import('./pages/TaskCenter/TaskCenter'));
const ScheduleCalendar = lazy(() => import('./pages/ScheduleCalendar/ScheduleCalendar'));
const BloggerLibrary = lazy(() => import('./pages/BloggerLibrary/BloggerLibrary'));
const PlanWorkspace = lazy(() => import('./pages/PlanWorkspace/PlanWorkspace'));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail/ProjectDetail'));
const ScriptExtraction = lazy(() => import('./pages/ScriptExtraction/ScriptExtraction'));
const VideoDownloader = lazy(() => import('./pages/VideoDownloader/VideoDownloader'));
const Settings = lazy(() => import('./pages/Settings/Settings'));
const UserManagement = lazy(() => import('./pages/UserManagement/UserManagement'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30000 },
  },
});

const navItems = [
  { to: '/', label: '数据看板', icon: LayoutDashboard, exact: true, adminOnly: false },
  { to: '/schedule', label: '日历排期', icon: Calendar, adminOnly: false },
  { to: '/planning', label: '账号策划', icon: Sparkles, adminOnly: false },
  { to: '/script-extraction', label: '脚本拆解', icon: RefreshCw, adminOnly: false },
  { to: '/bloggers', label: '博主智库', icon: Users, adminOnly: false },
  { to: '/downloader', label: '无水下载', icon: Download, adminOnly: false },
  { to: '/tasks', label: '任务中心', icon: Clock, adminOnly: false },
  { to: '/users', label: '用户管理', icon: Users, adminOnly: true },
  { to: '/settings', label: '系统设置', icon: SettingsIcon, adminOnly: true },
];

function AccessDenied({ title = '权限不足', description = '当前账号没有访问该页面的权限，请联系管理员开通。' }: { title?: string; description?: string }) {
  return (
    <div className="auth-page">
      <div className="access-denied-card">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </div>
  );
}

function MiniEye({
  mouseX,
  mouseY,
  maxDistance = 4,
  isBlinking = false,
  forceLookX,
  forceLookY,
}: {
  mouseX: number;
  mouseY: number;
  maxDistance?: number;
  isBlinking?: boolean;
  forceLookX?: number;
  forceLookY?: number;
}) {
  const pos = useMemo(() => {
    if (forceLookX !== undefined && forceLookY !== undefined) {
      return { x: forceLookX, y: forceLookY };
    }
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const dx = mouseX - cx;
    const dy = mouseY - cy;
    const distance = Math.min(Math.hypot(dx, dy), maxDistance);
    const angle = Math.atan2(dy, dx);
    return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
  }, [mouseX, mouseY, maxDistance, forceLookX, forceLookY]);

  return (
    <div className="sidebar-mini-eye" style={{ height: isBlinking ? 2 : 12 }}>
      {!isBlinking && (
        <div
          className="sidebar-mini-pupil"
          style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
        />
      )}
    </div>
  );
}

function SidebarMascot() {
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  const [isBlinking, setIsBlinking] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => setMouse({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    let blinkTimer: number;
    let closeTimer: number;
    const scheduleBlink = () => {
      blinkTimer = window.setTimeout(() => {
        setIsBlinking(true);
        closeTimer = window.setTimeout(() => setIsBlinking(false), 140);
        scheduleBlink();
      }, Math.random() * 3600 + 2400);
    };
    scheduleBlink();
    return () => {
      window.clearTimeout(blinkTimer);
      window.clearTimeout(closeTimer);
    };
  }, []);

  useEffect(() => {
    const onFocusIn = (e: FocusEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.matches('input, textarea, select, [contenteditable="true"]')) {
        setIsInputFocused(true);
      }
    };
    const onFocusOut = () => setIsInputFocused(false);
    window.addEventListener('focusin', onFocusIn);
    window.addEventListener('focusout', onFocusOut);
    return () => {
      window.removeEventListener('focusin', onFocusIn);
      window.removeEventListener('focusout', onFocusOut);
    };
  }, []);

  return (
    <div className="sidebar-mascot" aria-hidden="true">
      <div className="sidebar-mascot-char sidebar-char-a">
        <div className="sidebar-mascot-eyes">
          <MiniEye
            mouseX={mouse.x}
            mouseY={mouse.y}
            isBlinking={isBlinking}
            forceLookX={isInputFocused ? 4 : undefined}
            forceLookY={isInputFocused ? -2 : undefined}
          />
          <MiniEye
            mouseX={mouse.x}
            mouseY={mouse.y}
            isBlinking={isBlinking}
            forceLookX={isInputFocused ? 4 : undefined}
            forceLookY={isInputFocused ? -2 : undefined}
          />
        </div>
      </div>
      <div className="sidebar-mascot-char sidebar-char-b">
        <div className="sidebar-mascot-eyes">
          <MiniEye
            mouseX={mouse.x}
            mouseY={mouse.y}
            isBlinking={isBlinking}
            forceLookX={isInputFocused ? 3 : undefined}
            forceLookY={isInputFocused ? -1 : undefined}
          />
          <MiniEye
            mouseX={mouse.x}
            mouseY={mouse.y}
            isBlinking={isBlinking}
            forceLookX={isInputFocused ? 3 : undefined}
            forceLookY={isInputFocused ? -1 : undefined}
          />
        </div>
      </div>
      <div className="sidebar-mascot-char sidebar-char-c">
        <div className="sidebar-mascot-eyes">
          <MiniEye
            mouseX={mouse.x}
            mouseY={mouse.y}
            isBlinking={isBlinking}
            forceLookX={isInputFocused ? 5 : undefined}
            forceLookY={isInputFocused ? -2 : undefined}
          />
          <MiniEye
            mouseX={mouse.x}
            mouseY={mouse.y}
            isBlinking={isBlinking}
            forceLookX={isInputFocused ? 5 : undefined}
            forceLookY={isInputFocused ? -2 : undefined}
          />
        </div>
      </div>
    </div>
  );
}

function Layout({
  children,
  onLogout,
  currentUser,
}: {
  children: React.ReactNode;
  onLogout: () => void;
  currentUser: CurrentUserResponse;
}) {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const roleText = currentUser.role === 'admin' ? '管理员' : currentUser.role === 'member' ? '成员' : '访客';
  const visibleNavItems = navItems.filter((item) => !item.adminOnly || currentUser.role === 'admin');

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <AppLogo size={36} />
          </div>
          <div>
            <div className="logo-title">策划工作台</div>
            <div className="logo-sub">Douyin Creator</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {visibleNavItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'nav-item-active' : ''}`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
              {location.pathname === to && <ChevronRight size={14} className="nav-chevron" />}
            </NavLink>
          ))}
          <SidebarMascot />
        </nav>

        <div className="sidebar-footer">
          <button
            onClick={toggleTheme}
            className="nav-item sidebar-footer-btn w-full flex items-center justify-start border-none bg-transparent"
            title={theme === 'light' ? '深色模式' : '浅色模式'}
          >
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            <span>{theme === 'light' ? '深色模式' : '浅色模式'}</span>
          </button>

          <button
            onClick={onLogout}
            className="nav-item sidebar-footer-btn sidebar-footer-btn-last w-full flex items-center justify-start border-none bg-transparent"
            title="退出登录"
          >
            <LogOut size={18} />
            <span>退出登录</span>
          </button>

          <div className="version-tag">v1.0.0</div>
          <div className={`role-tag role-tag-${currentUser.role}`}>{roleText} · {currentUser.username}</div>
        </div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

function LoginView() {
  const qc = useQueryClient();

  const loginMutation = useMutation({
    mutationFn: (payload: { username: string; password: string }) => authApi.login(payload),
    onSuccess: (res) => {
      void res;
      qc.invalidateQueries({ queryKey: ['auth-me'] });
    },
  });

  return (
    <AnimatedLoginPage
      isSubmitting={loginMutation.isPending}
      onLogin={async (payload) => {
        await loginMutation.mutateAsync(payload);
      }}
    />
  );
}

function RouteLoadingFallback() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      页面加载中...
    </div>
  );
}

function AppContent() {
  const qc = useQueryClient();

  const meQuery = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => authApi.me(),
    retry: false,
  });

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // 忽略退出接口异常，前端仍然执行本地会话清理
    }
    qc.removeQueries({ queryKey: ['auth-me'] });
    qc.clear();
    window.location.href = '/';
  };

  if (meQuery.isLoading) {
    return (
      <div className="auth-page">
        <div className="loading">校验登录状态...</div>
      </div>
    );
  }

  if (meQuery.isError) {
    return <LoginView />;
  }

  const currentUser = meQuery.data;
  if (!currentUser) {
    return <LoginView />;
  }

  if (currentUser.role === 'viewer') {
    return (
      <Layout
        onLogout={handleLogout}
        currentUser={currentUser}
      >
        <AccessDenied
          title="访客账号暂不可用"
          description="当前系统已开启安全模式，访客账号暂不开放业务模块。请联系管理员升级为成员账号。"
        />
      </Layout>
    );
  }

  return (
    <Layout
      onLogout={handleLogout}
      currentUser={currentUser}
    >
      <Suspense fallback={<RouteLoadingFallback />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tasks" element={<TaskCenter />} />
          <Route path="/schedule" element={<ScheduleCalendar />} />
          <Route path="/bloggers" element={<BloggerLibrary />} />
          <Route path="/planning" element={<PlanWorkspace />} />
          <Route path="/planning/:id" element={<ProjectDetail />} />
          <Route path="/script-extraction" element={<ScriptExtraction />} />
          <Route path="/downloader" element={<VideoDownloader />} />
          <Route
            path="/users"
            element={currentUser.role === 'admin'
              ? <UserManagement />
              : <AccessDenied />}
          />
          <Route path="/logs" element={<Navigate to="/tasks" replace />} />
          <Route
            path="/settings"
            element={currentUser.role === 'admin'
              ? <Settings />
              : <AccessDenied />}
          />
        </Routes>
      </Suspense>
    </Layout>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <Router>
          <AppContent />
          <GlobalToaster />
        </Router>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
