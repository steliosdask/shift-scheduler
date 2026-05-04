// Theme constants based on /app/design_guidelines.json
export const Theme = {
  colors: {
    bg: '#FAFAF9',
    surface: '#FFFFFF',
    surfaceRaised: '#F3F4F6',
    overlay: 'rgba(0,0,0,0.5)',
    textPrimary: '#0A0D0A',
    textSecondary: '#4B5563',
    textDisabled: '#9CA3AF',
    textInverse: '#FFFFFF',
    border: '#E5E7EB',
    borderFocus: '#111827',
    brand: '#111827',
    brandHover: '#374151',
    hardBg: '#FEF2F2',
    hardBorder: '#EF4444',
    hardText: '#991B1B',
    softBg: '#FEF9C3',
    softBorder: '#EAB308',
    softText: '#854D0E',
    okBg: '#DCFCE7',
    okBorder: '#22C55E',
    okText: '#166534',
    pagniBg: '#EFF6FF',
    pagniText: '#1E40AF',
    pagniBorder: '#BFDBFE',
    venizeleioBg: '#F3F4F6',
    venizeleioText: '#4B5563',
    venizeleioBorder: '#D1D5DB',
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },
  radius: {
    sm: 6,
    md: 10,
    lg: 16,
  },
  font: {
    // System fonts fallback (Greek-supporting). Can be replaced with Fira Sans / IBM Plex if added.
    regular: undefined,
    bold: undefined,
  },
};

export const GREEK_MONTHS = [
  '', 'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος', 'Μάιος', 'Ιούνιος',
  'Ιούλιος', 'Αύγουστος', 'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος',
];

export const GREEK_DAYS_SHORT = ['Κυρ', 'Δευ', 'Τρι', 'Τετ', 'Πεμ', 'Παρ', 'Σαβ'];
export const GREEK_DAYS_LONG = ['Κυριακή', 'Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο'];
