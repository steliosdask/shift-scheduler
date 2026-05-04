import { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Theme, GREEK_MONTHS, GREEK_DAYS_SHORT } from '../../constants/Theme';
import { api, formatApiError } from '../../lib/api';

const STEPS = ['Μήνας', 'Γιατροί', 'Ημέρες', 'Άδειες'];

type Doctor = { id: string; full_name: string; is_active: boolean };
type DayDef = { date: string; type: 'open' | 'closed'; is_weekend?: boolean; is_holiday?: boolean };
type Constraint = {
  doctor_id: string;
  is_participating: boolean;
  negative_days: string[];
  leaves: { start_date: string; end_date: string; reason?: string }[];
};

const todayY = new Date().getFullYear();
const todayM = new Date().getMonth() + 1;

function buildDefaultDays(year: number, month: number): DayDef[] {
  const last = new Date(year, month, 0).getDate();
  const out: DayDef[] = [];
  for (let d = 1; d <= last; d++) {
    const dt = new Date(year, month - 1, d);
    out.push({
      date: `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      type: d % 2 === 1 ? 'open' : 'closed',
      is_weekend: dt.getDay() === 0 || dt.getDay() === 6,
    });
  }
  return out;
}

export default function Wizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [year, setYear] = useState(todayY);
  const [month, setMonth] = useState(todayM === 12 ? 1 : todayM + 1);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [holidays, setHolidays] = useState<Record<string, string>>({});
  const [days, setDays] = useState<DayDef[]>(buildDefaultDays(todayY, todayM === 12 ? 1 : todayM + 1));
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [activeDoctor, setActiveDoctor] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [d, h] = await Promise.all([api.get('/doctors'), api.get(`/holidays/${year}`)]);
        setDoctors(d.data);
        const map: Record<string, string> = {};
        h.data.holidays.forEach((x: any) => { map[x.date] = x.name; });
        setHolidays(map);
        setConstraints(
          d.data.map((doc: Doctor) => ({
            doctor_id: doc.id,
            is_participating: doc.is_active,
            negative_days: [],
            leaves: [],
          }))
        );
      } catch (e) {
        Alert.alert('Σφάλμα', formatApiError(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [year]);

  useEffect(() => {
    setDays(buildDefaultDays(year, month));
  }, [year, month]);

  const toggleParticipation = (id: string) => {
    setConstraints((prev) =>
      prev.map((c) => (c.doctor_id === id ? { ...c, is_participating: !c.is_participating } : c))
    );
  };

  const toggleDayType = (date: string) => {
    setDays((prev) => prev.map((d) => (d.date === date ? { ...d, type: d.type === 'open' ? 'closed' : 'open' } : d)));
  };

  const setAllAlternating = (startOpen: boolean) => {
    setDays((prev) => prev.map((d, i) => ({ ...d, type: (i % 2 === 0) === startOpen ? 'open' : 'closed' })));
  };

  const toggleNegativeDay = (doctorId: string, date: string) => {
    setConstraints((prev) =>
      prev.map((c) => {
        if (c.doctor_id !== doctorId) return c;
        const has = c.negative_days.includes(date);
        return {
          ...c,
          negative_days: has ? c.negative_days.filter((x) => x !== date) : [...c.negative_days, date],
        };
      })
    );
  };

  const onCreate = async () => {
    setCreating(true);
    try {
      // 1. Create schedule
      const r = await api.post('/schedules', { year, month });
      const scheduleId = r.data.id;
      // 2. Update with day_definitions, doctor_constraints
      await api.put(`/schedules/${scheduleId}`, {
        day_definitions: days,
        doctor_constraints: constraints,
      });
      // 3. Auto-generate
      try {
        await api.post(`/schedules/${scheduleId}/generate`);
      } catch (e: any) {
        // Allow user to continue even if generation fails
        Alert.alert(
          'Αυτόματη δημιουργία',
          formatApiError(e) + '\n\nΘα μεταβείτε στην επεξεργασία για χειροκίνητη ανάθεση.'
        );
      }
      router.replace(`/(app)/schedule/${scheduleId}`);
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    } finally {
      setCreating(false);
    }
  };

  const activeCount = constraints.filter((c) => c.is_participating).length;
  const monthNumDays = days.length;

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator size="large" color={Theme.colors.brand} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity testID="wizard-back-btn" onPress={() => (step === 0 ? router.back() : setStep(step - 1))} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={Theme.colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.title}>Νέο Πρόγραμμα</Text>
        <View style={styles.iconBtn} />
      </View>

      {/* Stepper */}
      <View style={styles.stepper}>
        {STEPS.map((label, idx) => (
          <View key={label} style={styles.stepItem}>
            <View style={[styles.stepCircle, idx <= step && styles.stepCircleActive]}>
              <Text style={[styles.stepNum, idx <= step && styles.stepNumActive]}>{idx + 1}</Text>
            </View>
            <Text style={[styles.stepLabel, idx === step && styles.stepLabelActive]}>{label}</Text>
          </View>
        ))}
      </View>

      <ScrollView contentContainerStyle={{ padding: Theme.spacing.md, paddingBottom: 100 }}>
        {step === 0 && (
          <View>
            <Text style={styles.h2}>Επιλέξτε Μήνα & Έτος</Text>
            <Text style={styles.help}>Για ποιον μήνα θα δημιουργήσετε πρόγραμμα εφημεριών;</Text>

            <Text style={styles.label}>Μήνας</Text>
            <View style={styles.chipsWrap}>
              {GREEK_MONTHS.slice(1).map((m, idx) => (
                <TouchableOpacity
                  key={m}
                  testID={`month-${idx + 1}`}
                  onPress={() => setMonth(idx + 1)}
                  style={[styles.chip, month === idx + 1 && styles.chipActive]}
                >
                  <Text style={[styles.chipText, month === idx + 1 && styles.chipTextActive]}>{m.slice(0, 3)}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.label}>Έτος</Text>
            <View style={styles.chipsWrap}>
              {[todayY - 1, todayY, todayY + 1].map((y) => (
                <TouchableOpacity
                  key={y}
                  testID={`year-${y}`}
                  onPress={() => setYear(y)}
                  style={[styles.chip, year === y && styles.chipActive]}
                >
                  <Text style={[styles.chipText, year === y && styles.chipTextActive]}>{y}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={styles.summaryBox}>
              <Text style={styles.summaryEyebrow}>Επιλογή</Text>
              <Text style={styles.summaryText}>
                {GREEK_MONTHS[month]} {year} — {monthNumDays} ημέρες
              </Text>
            </View>
          </View>
        )}

        {step === 1 && (
          <View>
            <Text style={styles.h2}>Επιβεβαίωση Γιατρών</Text>
            <Text style={styles.help}>Επιλέξτε ποιοι γιατροί θα συμμετέχουν στο πρόγραμμα ({activeCount}/{doctors.length})</Text>
            {doctors.map((d) => {
              const c = constraints.find((x) => x.doctor_id === d.id);
              return (
                <View key={d.id} style={styles.docRow} testID={`doctor-toggle-${d.id}`}>
                  <View style={styles.avatar}>
                    <Text style={styles.avatarText}>
                      {d.full_name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
                    </Text>
                  </View>
                  <Text style={styles.docName}>{d.full_name}</Text>
                  <Switch
                    value={c?.is_participating ?? false}
                    onValueChange={() => toggleParticipation(d.id)}
                    trackColor={{ false: Theme.colors.border, true: Theme.colors.brand }}
                  />
                </View>
              );
            })}
          </View>
        )}

        {step === 2 && (
          <View>
            <Text style={styles.h2}>Ανοιχτές / Κλειστές Ημέρες</Text>
            <Text style={styles.help}>
              Πατήστε σε κάθε ημέρα για εναλλαγή: <Text style={{ color: Theme.colors.pagniText, fontWeight: '700' }}>Α</Text> = Ανοιχτή (ΠΑΓΝΗ, 2 γιατροί), <Text style={{ fontWeight: '700' }}>Κ</Text> = Κλειστή (ΒΕΝΙΖΕΛΕΙΟ, 1 γιατρός)
            </Text>
            <View style={styles.bulkRow}>
              <TouchableOpacity
                testID="bulk-alt-open"
                onPress={() => setAllAlternating(true)}
                style={[styles.btn, styles.btnGhost, { flex: 1 }]}
              >
                <Text style={styles.btnGhostText}>Α/Κ από 1η</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="bulk-alt-closed"
                onPress={() => setAllAlternating(false)}
                style={[styles.btn, styles.btnGhost, { flex: 1 }]}
              >
                <Text style={styles.btnGhostText}>Κ/Α από 1η</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.dayGrid}>
              <View style={styles.weekRow}>
                {GREEK_DAYS_SHORT.map((dn) => (
                  <Text key={dn} style={styles.weekHead}>{dn}</Text>
                ))}
              </View>
              <DayCalendarGrid
                year={year}
                month={month}
                days={days}
                holidays={holidays}
                onPressDay={toggleDayType}
              />
            </View>
          </View>
        )}

        {step === 3 && (
          <View>
            <Text style={styles.h2}>Αρνητικές Ημέρες & Άδειες</Text>
            <Text style={styles.help}>
              Επιλέξτε γιατρό και πατήστε στις ημέρες που δεν είναι διαθέσιμος/η.
            </Text>
            <View style={styles.chipsWrap}>
              {constraints.filter((c) => c.is_participating).map((c) => {
                const doc = doctors.find((d) => d.id === c.doctor_id)!;
                const isActive = activeDoctor === c.doctor_id;
                return (
                  <TouchableOpacity
                    key={c.doctor_id}
                    testID={`select-doctor-${c.doctor_id}`}
                    style={[styles.chip, isActive && styles.chipActive]}
                    onPress={() => setActiveDoctor(c.doctor_id)}
                  >
                    <Text style={[styles.chipText, isActive && styles.chipTextActive]}>
                      {doc.full_name.split(' ')[0]}
                      {c.negative_days.length > 0 ? ` (${c.negative_days.length})` : ''}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            {activeDoctor ? (
              <View style={styles.dayGrid}>
                <View style={styles.weekRow}>
                  {GREEK_DAYS_SHORT.map((dn) => (
                    <Text key={dn} style={styles.weekHead}>{dn}</Text>
                  ))}
                </View>
                <DayCalendarGrid
                  year={year}
                  month={month}
                  days={days}
                  holidays={holidays}
                  negativeDays={
                    constraints.find((c) => c.doctor_id === activeDoctor)?.negative_days || []
                  }
                  onPressDay={(date) => toggleNegativeDay(activeDoctor, date)}
                  showNegative
                />
              </View>
            ) : (
              <Text style={styles.help}>Επιλέξτε έναν γιατρό από τα παραπάνω.</Text>
            )}
          </View>
        )}
      </ScrollView>

      <View style={styles.footer}>
        {step < 3 ? (
          <TouchableOpacity
            testID="wizard-next-btn"
            style={[styles.btn, styles.btnPrimary]}
            onPress={() => setStep(step + 1)}
            disabled={step === 1 && activeCount === 0}
          >
            <Text style={styles.btnPrimaryText}>Επόμενο</Text>
            <Ionicons name="arrow-forward" size={18} color={Theme.colors.textInverse} />
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            testID="wizard-create-btn"
            style={[styles.btn, styles.btnPrimary, creating && { opacity: 0.6 }]}
            onPress={onCreate}
            disabled={creating}
          >
            {creating ? (
              <ActivityIndicator color={Theme.colors.textInverse} />
            ) : (
              <>
                <Text style={styles.btnPrimaryText}>Δημιουργία Προγράμματος</Text>
                <Ionicons name="sparkles" size={18} color={Theme.colors.textInverse} />
              </>
            )}
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

function DayCalendarGrid({
  year,
  month,
  days,
  holidays,
  negativeDays = [],
  onPressDay,
  showNegative = false,
}: {
  year: number;
  month: number;
  days: DayDef[];
  holidays: Record<string, string>;
  negativeDays?: string[];
  onPressDay: (date: string) => void;
  showNegative?: boolean;
}) {
  const first = new Date(year, month - 1, 1);
  const leading = first.getDay(); // Sun=0
  const cells: (DayDef | null)[] = [];
  for (let i = 0; i < leading; i++) cells.push(null);
  days.forEach((d) => cells.push(d));
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (DayDef | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <View>
      {weeks.map((wk, wIdx) => (
        <View key={wIdx} style={{ flexDirection: 'row' }}>
          {wk.map((d, cIdx) => {
            if (!d) return <View key={cIdx} style={[styles.dayCell, { backgroundColor: 'transparent', borderColor: 'transparent' }]} />;
            const isWeekend = d.is_weekend;
            const isHoliday = !!holidays[d.date];
            const isNeg = negativeDays.includes(d.date);
            const num = parseInt(d.date.slice(8), 10);
            const cellBg = showNegative
              ? isNeg
                ? Theme.colors.hardBg
                : isHoliday
                ? Theme.colors.softBg
                : isWeekend
                ? '#FEF2F2'
                : Theme.colors.surface
              : d.type === 'open'
              ? Theme.colors.pagniBg
              : Theme.colors.venizeleioBg;
            return (
              <TouchableOpacity
                key={cIdx}
                testID={`cal-${d.date}`}
                onPress={() => onPressDay(d.date)}
                style={[styles.dayCell, { backgroundColor: cellBg }]}
                activeOpacity={0.7}
              >
                <Text style={[styles.dayNum, isHoliday && { color: Theme.colors.softText }]}>{num}</Text>
                {showNegative ? (
                  isNeg ? (
                    <Ionicons name="close-circle" size={14} color={Theme.colors.hardBorder} />
                  ) : null
                ) : (
                  <Text style={[styles.dayType, d.type === 'open' ? { color: Theme.colors.pagniText } : { color: Theme.colors.venizeleioText }]}>
                    {d.type === 'open' ? 'Α' : 'Κ'}
                  </Text>
                )}
                {isHoliday && !showNegative && (
                  <View style={styles.holidayDot} />
                )}
              </TouchableOpacity>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Theme.colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: Theme.spacing.md, paddingTop: Theme.spacing.md, gap: 12,
  },
  title: { flex: 1, fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary, textAlign: 'center' },
  iconBtn: {
    width: 40, height: 40, borderRadius: Theme.radius.md,
    borderWidth: 1, borderColor: Theme.colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  stepper: {
    flexDirection: 'row', justifyContent: 'space-around', paddingVertical: Theme.spacing.md,
    paddingHorizontal: Theme.spacing.sm, borderBottomWidth: 1, borderBottomColor: Theme.colors.border,
  },
  stepItem: { alignItems: 'center', gap: 4 },
  stepCircle: {
    width: 28, height: 28, borderRadius: 14, borderWidth: 1.5, borderColor: Theme.colors.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.surface,
  },
  stepCircleActive: { borderColor: Theme.colors.brand, backgroundColor: Theme.colors.brand },
  stepNum: { fontSize: 12, fontWeight: '700', color: Theme.colors.textDisabled },
  stepNumActive: { color: Theme.colors.textInverse },
  stepLabel: { fontSize: 10, color: Theme.colors.textDisabled, fontWeight: '600' },
  stepLabelActive: { color: Theme.colors.textPrimary },
  h2: { fontSize: 22, fontWeight: '700', color: Theme.colors.textPrimary, marginBottom: 4 },
  help: { fontSize: 13, color: Theme.colors.textSecondary, marginBottom: Theme.spacing.lg },
  label: { fontSize: 11, fontWeight: '700', color: Theme.colors.textSecondary, letterSpacing: 1.2, textTransform: 'uppercase', marginTop: Theme.spacing.md, marginBottom: 8 },
  chipsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: Theme.radius.sm,
    borderWidth: 1, borderColor: Theme.colors.border, backgroundColor: Theme.colors.surface,
  },
  chipActive: { backgroundColor: Theme.colors.brand, borderColor: Theme.colors.brand },
  chipText: { fontSize: 13, fontWeight: '600', color: Theme.colors.textPrimary },
  chipTextActive: { color: Theme.colors.textInverse },
  summaryBox: {
    marginTop: Theme.spacing.xl, padding: Theme.spacing.md,
    borderWidth: 1, borderColor: Theme.colors.border, borderRadius: Theme.radius.md,
    backgroundColor: Theme.colors.surfaceRaised,
  },
  summaryEyebrow: { fontSize: 10, fontWeight: '700', color: Theme.colors.textSecondary, letterSpacing: 1.5, textTransform: 'uppercase' },
  summaryText: { fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary, marginTop: 4 },
  docRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: Theme.colors.border,
  },
  avatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: Theme.colors.surfaceRaised, alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontSize: 12, fontWeight: '700', color: Theme.colors.textPrimary },
  docName: { flex: 1, fontSize: 15, color: Theme.colors.textPrimary, fontWeight: '500' },
  bulkRow: { flexDirection: 'row', gap: 8, marginBottom: Theme.spacing.md },
  dayGrid: { marginTop: Theme.spacing.md },
  weekRow: { flexDirection: 'row', marginBottom: 4 },
  weekHead: {
    flex: 1, fontSize: 10, fontWeight: '700', color: Theme.colors.textSecondary,
    letterSpacing: 1, textAlign: 'center', textTransform: 'uppercase',
  },
  dayCell: {
    flex: 1, aspectRatio: 1, borderWidth: 1, borderColor: Theme.colors.border,
    margin: 2, borderRadius: 6, alignItems: 'center', justifyContent: 'center', position: 'relative',
  },
  dayNum: { fontSize: 14, fontWeight: '700', color: Theme.colors.textPrimary },
  dayType: { fontSize: 10, fontWeight: '700', marginTop: 2 },
  holidayDot: {
    position: 'absolute', top: 4, right: 4,
    width: 6, height: 6, borderRadius: 3, backgroundColor: Theme.colors.softBorder,
  },
  footer: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: Theme.colors.surface, padding: Theme.spacing.md,
    borderTopWidth: 1, borderTopColor: Theme.colors.border,
  },
  btn: {
    flexDirection: 'row', paddingVertical: 14, borderRadius: Theme.radius.md,
    alignItems: 'center', justifyContent: 'center', gap: 8,
  },
  btnGhost: { borderWidth: 1, borderColor: Theme.colors.border },
  btnGhostText: { color: Theme.colors.textPrimary, fontWeight: '600', fontSize: 13 },
  btnPrimary: { backgroundColor: Theme.colors.brand },
  btnPrimaryText: { color: Theme.colors.textInverse, fontWeight: '700', fontSize: 15 },
});
