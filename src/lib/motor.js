// The API stores a machine's rating in kW (`ratedKw`); operators think of
// motors in horsepower. 1 mechanical HP = 0.7457 kW.
export const KW_PER_HP = 0.7457;
export const MAX_HP = 1000;

export const kwToHp = (kw) => Math.round((kw / KW_PER_HP) * 10) / 10;

export const hpToKw = (hp) => Math.round(hp * KW_PER_HP * 1000) / 1000;

export function parseHp(text) {
  const s = String(text ?? "").trim();
  if (!/^\d+(\.\d)?$/.test(s)) return null;
  const n = Number(s);
  return n > 0 && n <= MAX_HP ? n : null;
}
