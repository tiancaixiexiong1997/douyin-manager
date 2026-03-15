import { useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import { notifyEventName, type NotifyType } from '../utils/notify';

type Toast = {
  id: number;
  type: NotifyType;
  message: string;
  duration: number;
};

export function GlobalToaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    let seed = 0;
    const handler = (event: Event) => {
      const custom = event as CustomEvent<{ type?: NotifyType; message: string; duration?: number }>;
      const message = custom.detail?.message?.trim();
      if (!message) return;

      const toast: Toast = {
        id: ++seed,
        type: custom.detail?.type || 'info',
        message,
        duration: custom.detail?.duration ?? 2600,
      };

      setToasts((prev) => [...prev, toast].slice(-3));

      window.setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== toast.id));
      }, toast.duration);
    };

    window.addEventListener(notifyEventName, handler as EventListener);
    return () => window.removeEventListener(notifyEventName, handler as EventListener);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="global-toast-wrap" aria-live="polite" aria-atomic="true">
      {toasts.map((toast) => (
        <div key={toast.id} className={`global-toast global-toast-${toast.type}`}>
          {toast.type === 'success' && <CheckCircle2 size={16} />}
          {toast.type === 'error' && <AlertTriangle size={16} />}
          {toast.type === 'info' && <Info size={16} />}
          <span>{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
