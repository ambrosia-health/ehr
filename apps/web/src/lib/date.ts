export function formatInTimeZone(
  value: string | Date,
  timeZone: string,
  options: Intl.DateTimeFormatOptions,
  locale = "en-US",
): string {
  const date = value instanceof Date
    ? value
    : new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  try {
    return new Intl.DateTimeFormat(locale, { ...options, timeZone }).format(date);
  } catch {
    return "Not recorded";
  }
}
