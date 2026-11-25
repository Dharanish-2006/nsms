// A colour sorter is not a motor load, so it has no power factor or production output.
export const hasPowerQuality = (m) => m.type !== "sortex";

export const utilisationPct = (running, consumed) =>
  consumed > 0 ? Math.min(100, Math.max(0, Math.round((running / consumed) * 100))) : null;
