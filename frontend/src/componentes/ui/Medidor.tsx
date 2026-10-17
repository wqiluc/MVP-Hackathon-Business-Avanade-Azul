interface MedidorProps {
  /** 0–1 */
  value: number;
  label: string;
  fill?: string;
  track?: string;
}

export function Medidor({ value, label, fill, track }: MedidorProps) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div
      className="meter"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      style={{ ['--meter-fill' as string]: fill, ['--meter-track' as string]: track }}
    >
      <div className="meter__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
