const BEIJING_TIME_ZONE = 'Asia/Shanghai';
const NAIVE_DATETIME_PATTERN = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;
const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function normalizeBackendDateInput(value: string): string {
  const raw = value.trim();
  if (!raw) return raw;
  if (DATE_ONLY_PATTERN.test(raw)) {
    return `${raw}T00:00:00`;
  }
  if (NAIVE_DATETIME_PATTERN.test(raw)) {
    return `${raw.replace(' ', 'T')}Z`;
  }
  return raw;
}

export function parseBackendDate(value?: string | null): Date | null {
  if (!value) return null;
  const normalized = normalizeBackendDateInput(String(value));
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

export function toBackendTimestamp(value?: string | null): number {
  return parseBackendDate(value)?.getTime() ?? 0;
}

export function formatBackendDateTime(
  value?: string | null,
  options: Intl.DateTimeFormatOptions = {},
  fallback = '-',
): string {
  const parsed = parseBackendDate(value);
  if (!parsed) return value || fallback;
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TIME_ZONE,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: options.second,
    ...options,
  }).format(parsed);
}

export function formatBackendDate(
  value?: string | null,
  options: Intl.DateTimeFormatOptions = {},
  fallback = '-',
): string {
  const parsed = parseBackendDate(value);
  if (!parsed) return value || fallback;
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    ...options,
  }).format(parsed);
}
