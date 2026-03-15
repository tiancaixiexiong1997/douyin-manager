export type NotifyType = 'success' | 'error' | 'info';

export interface NotifyPayload {
  type?: NotifyType;
  message: string;
  duration?: number;
}

const EVENT_NAME = 'app:notify';

export const notify = ({ type = 'info', message, duration = 2600 }: NotifyPayload) => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: { type, message, duration } }));
};

export const notifySuccess = (message: string, duration?: number) =>
  notify({ type: 'success', message, duration });

export const notifyError = (message: string, duration?: number) =>
  notify({ type: 'error', message, duration });

export const notifyInfo = (message: string, duration?: number) =>
  notify({ type: 'info', message, duration });

export const notifyEventName = EVENT_NAME;
