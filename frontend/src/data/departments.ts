/**
 * Symptom keyword -> department id. This is the ONLY hardcoded department
 * knowledge on the kiosk. Names, rooms, colours, icons and wait times come
 * from GET /departments (see useKioskStore.loadDepartments).
 */
export const SYMPTOM_KEYWORDS: Record<string, string> = {
  general: 'general', fever: 'general', headache: 'general', cough: 'general',
  cardio: 'cardio', chest: 'cardio', heart: 'cardio',
  ortho: 'ortho', bone: 'ortho', joint: 'ortho', fracture: 'ortho',
  paeds: 'paeds', child: 'paeds', baby: 'paeds',
  gyne: 'gyne', pregnancy: 'gyne',
  derm: 'derm', skin: 'derm', rash: 'derm',
  ent: 'ent', ear: 'ent', throat: 'ent',
  ophthal: 'ophthal', eye: 'ophthal', vision: 'ophthal',
};

export const DEFAULT_DEPT_ID = 'general';

export function detectDeptId(text: string): string {
  const lower = text.toLowerCase();
  for (const [kw, id] of Object.entries(SYMPTOM_KEYWORDS)) {
    if (lower.includes(kw)) return id;
  }
  return DEFAULT_DEPT_ID;
}
