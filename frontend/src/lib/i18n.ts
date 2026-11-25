// Centralized navigation copy; scientific content remains in its original language.
export const messages = {
  es: { library: 'Biblioteca', map: 'Geovisor', assistant: 'Asistente', taxonomy: 'Taxonomía', methodology: 'Metodología', local: 'Estación local' },
  en: { library: 'Library', map: 'Map explorer', assistant: 'Assistant', taxonomy: 'Taxonomy', methodology: 'Methodology', local: 'Local station' },
} as const;
export type Locale = keyof typeof messages;
