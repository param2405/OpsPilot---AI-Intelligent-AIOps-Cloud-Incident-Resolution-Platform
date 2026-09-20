type MarkProps = {
  size?: number;
};

export function Mark({ size = 34 }: MarkProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" fill="none" aria-hidden="true">
      <rect width="34" height="34" rx="8" fill="#2a221c" />
      <circle cx="17" cy="17" r="10" stroke="#d4784a" strokeWidth="1.4" />
      <circle cx="17" cy="17" r="5" stroke="#f3ece4" strokeWidth="1.1" opacity="0.7" />
      <path d="M17 6.5v4.2M17 23.3V27.5M6.5 17h4.2M23.3 17H27.5" stroke="#d4784a" strokeWidth="1.2" />
    </svg>
  );
}
