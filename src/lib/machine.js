// A colour sorter is not a motor load, so it has no power factor or load factor.
export const hasPowerQuality = (m) => m.type !== "sortex";
