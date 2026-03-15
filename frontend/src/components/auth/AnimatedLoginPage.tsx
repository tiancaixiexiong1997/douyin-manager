import { useEffect, useMemo, useRef, useState } from 'react';
import { Eye, EyeOff, ShieldCheck, Sparkles, User, X } from 'lucide-react';
import wechatQr from '../../assets/contact-wechat-qr.jpg';
import './AnimatedLoginPage.css';

type LoginPayload = {
  username: string;
  password: string;
};

type AnimatedLoginPageProps = {
  onLogin: (payload: LoginPayload) => Promise<void>;
  isSubmitting?: boolean;
};

const LOGIN_RECENT_USERS_KEY = 'login_recent_usernames';
const LOGIN_REMEMBER_ME_KEY = 'login_remember_me';
const LOGIN_REMEMBERED_USER_KEY = 'login_remembered_username';

const readRecentUsers = (): string[] => {
  try {
    const raw = localStorage.getItem(LOGIN_RECENT_USERS_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw) as string[];
    return Array.isArray(list) ? list.filter((item) => typeof item === 'string' && item.trim()) : [];
  } catch {
    return [];
  }
};

const readRememberedUsername = () => {
  const remember = localStorage.getItem(LOGIN_REMEMBER_ME_KEY);
  if (remember === 'false') return '';
  return localStorage.getItem(LOGIN_REMEMBERED_USER_KEY) || '';
};

type EyeBallProps = {
  size?: number;
  pupilSize?: number;
  maxDistance?: number;
  isBlinking?: boolean;
  forceLookX?: number;
  forceLookY?: number;
};

function EyeBall({
  size = 20,
  pupilSize = 8,
  maxDistance = 5,
  isBlinking = false,
  forceLookX,
  forceLookY,
}: EyeBallProps) {
  const [mouse, setMouse] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => setMouse({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const pos = useMemo(() => {
    if (forceLookX !== undefined && forceLookY !== undefined) return { x: forceLookX, y: forceLookY };
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const dx = mouse.x - cx;
    const dy = mouse.y - cy;
    const distance = Math.min(Math.hypot(dx, dy), maxDistance);
    const angle = Math.atan2(dy, dx);
    return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
  }, [mouse, maxDistance, forceLookX, forceLookY]);

  return (
    <div
      className="anim-eye"
      style={{
        width: size,
        height: isBlinking ? 2 : size,
      }}
    >
      {!isBlinking && (
        <div
          className="anim-pupil"
          style={{
            width: pupilSize,
            height: pupilSize,
            transform: `translate(${pos.x}px, ${pos.y}px)`,
          }}
        />
      )}
    </div>
  );
}

type DotPupilProps = {
  size?: number;
  maxDistance?: number;
  forceLookX?: number;
  forceLookY?: number;
};

function DotPupil({ size = 12, maxDistance = 5, forceLookX, forceLookY }: DotPupilProps) {
  const [mouse, setMouse] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => setMouse({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const pos = useMemo(() => {
    if (forceLookX !== undefined && forceLookY !== undefined) return { x: forceLookX, y: forceLookY };
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const dx = mouse.x - cx;
    const dy = mouse.y - cy;
    const distance = Math.min(Math.hypot(dx, dy), maxDistance);
    const angle = Math.atan2(dy, dx);
    return { x: Math.cos(angle) * distance, y: Math.sin(angle) * distance };
  }, [mouse, maxDistance, forceLookX, forceLookY]);

  return (
    <div
      className="anim-dot-pupil"
      style={{
        width: size,
        height: size,
        transform: `translate(${pos.x}px, ${pos.y}px)`,
      }}
    />
  );
}

export function AnimatedLoginPage({ onLogin, isSubmitting = false }: AnimatedLoginPageProps) {
  const [username, setUsername] = useState(() => readRememberedUsername() || 'admin');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(() => localStorage.getItem(LOGIN_REMEMBER_ME_KEY) !== 'false');
  const [recentUsers, setRecentUsers] = useState<string[]>(() => readRecentUsers().slice(0, 5));
  const [showPassword, setShowPassword] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [error, setError] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isLookingAtEachOther, setIsLookingAtEachOther] = useState(false);
  const [isPurplePeeking, setIsPurplePeeking] = useState(false);
  const [isPurpleBlinking, setIsPurpleBlinking] = useState(false);
  const [isBlackBlinking, setIsBlackBlinking] = useState(false);
  const [mouseX, setMouseX] = useState(0);
  const [mouseY, setMouseY] = useState(0);
  const lookTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMouseX(e.clientX);
      setMouseY(e.clientY);
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    const blink = () => {
      const timeout = setTimeout(() => {
        setIsPurpleBlinking(true);
        setTimeout(() => setIsPurpleBlinking(false), 150);
        blink();
      }, Math.random() * 4000 + 3000);
      return timeout;
    };
    const t = blink();
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const blink = () => {
      const timeout = setTimeout(() => {
        setIsBlackBlinking(true);
        setTimeout(() => setIsBlackBlinking(false), 150);
        blink();
      }, Math.random() * 4000 + 3000);
      return timeout;
    };
    const t = blink();
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    return () => {
      if (lookTimerRef.current !== null) {
        window.clearTimeout(lookTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!showContactModal) return;
    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowContactModal(false);
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeydown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeydown);
    };
  }, [showContactModal]);

  const triggerLookAtEachOther = () => {
    setIsLookingAtEachOther(true);
    if (lookTimerRef.current !== null) {
      window.clearTimeout(lookTimerRef.current);
    }
    lookTimerRef.current = window.setTimeout(() => {
      setIsLookingAtEachOther(false);
      lookTimerRef.current = null;
    }, 900);
  };

  useEffect(() => {
    if (password.length === 0 || !showPassword) {
      return;
    }
    const timer = setTimeout(() => {
      setIsPurplePeeking(true);
      setTimeout(() => setIsPurplePeeking(false), 800);
    }, Math.random() * 3000 + 2000);
    return () => clearTimeout(timer);
  }, [password, showPassword, isPurplePeeking]);

  const calc = (cx: number, cy: number) => {
    const dx = mouseX - cx;
    const dy = mouseY - cy;
    const faceX = Math.max(-15, Math.min(15, dx / 20));
    const faceY = Math.max(-10, Math.min(10, dy / 30));
    const bodySkew = Math.max(-6, Math.min(6, -dx / 120));
    return { faceX, faceY, bodySkew };
  };

  const purplePos = calc(220, 300);
  const blackPos = calc(300, 280);
  const yellowPos = calc(390, 300);
  const orangePos = calc(120, 340);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await onLogin({ username, password });
      const normalized = username.trim();
      if (normalized) {
        const nextRecent = [normalized, ...recentUsers.filter((item) => item !== normalized)].slice(0, 5);
        setRecentUsers(nextRecent);
        localStorage.setItem(LOGIN_RECENT_USERS_KEY, JSON.stringify(nextRecent));
        localStorage.setItem(LOGIN_REMEMBER_ME_KEY, rememberMe ? 'true' : 'false');
        if (rememberMe) {
          localStorage.setItem(LOGIN_REMEMBERED_USER_KEY, normalized);
        } else {
          localStorage.removeItem(LOGIN_REMEMBERED_USER_KEY);
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败，请重试';
      setError(message);
    }
  };

  return (
    <div className="anim-login-page">
      <div className="anim-left">
        <div className="anim-brand">
          <div className="anim-brand-icon"><Sparkles size={16} /></div>
          <span>抖音策划系统</span>
        </div>

        <div className="anim-stage-wrap">
          <div className="anim-stage">
            <div
              className="ch-purple"
              style={{
                height: (isTyping || (password.length > 0 && !showPassword)) ? 440 : 400,
                transform: (password.length > 0 && showPassword)
                  ? 'skewX(0deg)'
                  : (isTyping || (password.length > 0 && !showPassword))
                    ? `skewX(${purplePos.bodySkew - 12}deg) translateX(40px)`
                    : `skewX(${purplePos.bodySkew}deg)`,
              }}
            >
              <div
                className="eye-row"
                style={{
                  left: (password.length > 0 && showPassword) ? 20 : isLookingAtEachOther ? 55 : 45 + purplePos.faceX,
                  top: (password.length > 0 && showPassword) ? 35 : isLookingAtEachOther ? 65 : 40 + purplePos.faceY,
                  gap: 26,
                }}
              >
                <EyeBall
                  size={18}
                  pupilSize={7}
                  maxDistance={5}
                  isBlinking={isPurpleBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
                />
                <EyeBall
                  size={18}
                  pupilSize={7}
                  maxDistance={5}
                  isBlinking={isPurpleBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? (isPurplePeeking ? 4 : -4) : isLookingAtEachOther ? 3 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? (isPurplePeeking ? 5 : -4) : isLookingAtEachOther ? 4 : undefined}
                />
              </div>
            </div>

            <div
              className="ch-black"
              style={{
                transform: (password.length > 0 && showPassword)
                  ? 'skewX(0deg)'
                  : isLookingAtEachOther
                    ? `skewX(${blackPos.bodySkew * 1.5 + 10}deg) translateX(20px)`
                    : (isTyping || (password.length > 0 && !showPassword))
                      ? `skewX(${blackPos.bodySkew * 1.5}deg)`
                      : `skewX(${blackPos.bodySkew}deg)`,
              }}
            >
              <div
                className="eye-row"
                style={{
                  left: (password.length > 0 && showPassword) ? 10 : isLookingAtEachOther ? 32 : 26 + blackPos.faceX,
                  top: (password.length > 0 && showPassword) ? 28 : isLookingAtEachOther ? 12 : 32 + blackPos.faceY,
                  gap: 18,
                }}
              >
                <EyeBall
                  size={16}
                  pupilSize={6}
                  maxDistance={4}
                  isBlinking={isBlackBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? -4 : isLookingAtEachOther ? 0 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? -4 : isLookingAtEachOther ? -4 : undefined}
                />
                <EyeBall
                  size={16}
                  pupilSize={6}
                  maxDistance={4}
                  isBlinking={isBlackBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? -4 : isLookingAtEachOther ? 0 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? -4 : isLookingAtEachOther ? -4 : undefined}
                />
              </div>
            </div>

            <div
              className="ch-orange"
              style={{
                transform: (password.length > 0 && showPassword) ? 'skewX(0deg)' : `skewX(${orangePos.bodySkew}deg)`,
              }}
            >
              <div
                className="dot-eye-row"
                style={{
                  left: (password.length > 0 && showPassword) ? 50 : 82 + orangePos.faceX,
                  top: (password.length > 0 && showPassword) ? 85 : 90 + orangePos.faceY,
                  gap: 24,
                }}
              >
                <DotPupil size={12} maxDistance={5} forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? -4 : undefined} />
                <DotPupil size={12} maxDistance={5} forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? -4 : undefined} />
              </div>
            </div>

            <div
              className="ch-yellow"
              style={{
                transform: (password.length > 0 && showPassword) ? 'skewX(0deg)' : `skewX(${yellowPos.bodySkew}deg)`,
              }}
            >
              <div
                className="dot-eye-row"
                style={{
                  left: (password.length > 0 && showPassword) ? 20 : 52 + yellowPos.faceX,
                  top: (password.length > 0 && showPassword) ? 35 : 40 + yellowPos.faceY,
                  gap: 18,
                }}
              >
                <DotPupil size={12} maxDistance={5} forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? -4 : undefined} />
                <DotPupil size={12} maxDistance={5} forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? -4 : undefined} />
              </div>
              <div
                className="yellow-mouth"
                style={{
                  left: (password.length > 0 && showPassword) ? 10 : 40 + yellowPos.faceX,
                  top: (password.length > 0 && showPassword) ? 88 : 88 + yellowPos.faceY,
                }}
              />
            </div>
          </div>
        </div>

      </div>

      <div className="anim-right">
        <form className="anim-form" onSubmit={handleSubmit}>
          <div className="anim-login-head-badge"><ShieldCheck size={15} /> 安全登录</div>
          <h1>欢迎回来</h1>
          <p>请登录后访问全部系统功能</p>

          <label htmlFor="username">用户名</label>
          <div className="anim-input-wrap">
            <User size={16} className="anim-input-icon" />
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              list="anim-recent-usernames"
              onFocus={() => {
                setIsTyping(true);
                triggerLookAtEachOther();
              }}
              onBlur={() => {
                setIsTyping(false);
                setIsLookingAtEachOther(false);
                if (lookTimerRef.current !== null) {
                  window.clearTimeout(lookTimerRef.current);
                  lookTimerRef.current = null;
                }
              }}
              autoComplete="username"
              required
            />
            <datalist id="anim-recent-usernames">
              {recentUsers.map((item) => (
                <option value={item} key={item} />
              ))}
            </datalist>
          </div>

          <label htmlFor="password">密码</label>
          <div className="anim-input-wrap">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => {
                const next = e.target.value;
                setPassword(next);
                if (!next) {
                  setIsPurplePeeking(false);
                }
              }}
              autoComplete="current-password"
              required
            />
            <button
              type="button"
              className="anim-eye-toggle"
              onClick={() => {
                setShowPassword((v) => {
                  const next = !v;
                  if (!next) {
                    setIsPurplePeeking(false);
                  }
                  return next;
                });
              }}
              aria-label={showPassword ? '隐藏密码' : '显示密码'}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          {error && <div className="anim-error">{error}</div>}

          <div className="anim-login-options">
            <label className="anim-remember-check">
              <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
              记住账号
            </label>
          </div>

          {recentUsers.length > 0 && (
            <div className="anim-recent-users">
              <span>最近登录：</span>
              <div className="anim-recent-list">
                {recentUsers.map((item) => (
                  <button key={item} type="button" className="anim-recent-btn" onClick={() => setUsername(item)}>
                    {item}
                  </button>
                ))}
              </div>
            </div>
          )}

          <button className="anim-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? '登录中...' : '登录'}
          </button>

          <div className="anim-signup-hint">
            还没有账号？
            <button type="button" className="anim-contact-link" onClick={() => setShowContactModal(true)}>
              联系管理员开通
            </button>
          </div>
        </form>
      </div>

      {showContactModal && (
        <div className="anim-contact-backdrop" onClick={() => setShowContactModal(false)}>
          <div
            className="anim-contact-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="contact-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="anim-contact-close"
              aria-label="关闭弹窗"
              onClick={() => setShowContactModal(false)}
            >
              <X size={18} />
            </button>

            <div className="anim-contact-title-wrap">
              <h3 id="contact-modal-title">联系管理员开通账号</h3>
              <p>请使用微信扫码添加管理员，备注“抖音策划系统开通”</p>
            </div>

            <div className="anim-contact-qr-wrap">
              <img src={wechatQr} alt="管理员微信二维码" className="anim-contact-qr" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
