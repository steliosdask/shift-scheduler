import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
  Modal,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Theme, GREEK_MONTHS, GREEK_DAYS_SHORT, GREEK_DAYS_LONG } from '../../../constants/Theme';
import { api, formatApiError, getAuthToken } from '../../../lib/api';

type Schedule = {
  id: string;
  year: number;
  month: number;
  status: string;
  day_definitions: { date: string; type: string; is_weekend?: boolean; is_holiday?: boolean }[];
  shifts: { date: string; type: string; doctors: string[] }[];
};

type Doctor = { id: string; full_name: string };
type Validation = {
  hard: any[];
  soft: any[];
  per_day: Record<string, { hard: any[]; soft: any[] }>;
  per_doctor: Record<string, { name: string; shifts: number; weekends: number; holidays: number }>;
};

export default function ScheduleEdit() {
  const params = useLocalSearchParams();
  const id = params.id as string;
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [holidays, setHolidays] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validation, setValidation] = useState<Validation | null>(null);
  const [editDay, setEditDay] = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  const docMap = useMemo(() => Object.fromEntries(doctors.map((d) => [d.id, d.full_name])), [doctors]);

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api.get(`/schedules/${id}`), api.get('/doctors')]);
      setSchedule(s.data);
      setDoctors(d.data);
      const h = await api.get(`/holidays/${s.data.year}`);
      const map: Record<string, string> = {};
      h.data.holidays.forEach((x: any) => { map[x.date] = x.name; });
      setHolidays(map);
      runValidation(s.data.shifts || [], s.data);
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const runValidation = async (shifts: any[], sch?: Schedule) => {
    const sid = sch?.id || schedule?.id;
    if (!sid) return;
    try {
      const r = await api.post(`/schedules/${sid}/validate`, { shifts });
      setValidation(r.data);
    } catch {
      // Validation is informational; the schedule stays usable without it.
    }
  };

  const handleAssignDoctor = async (date: string, doctorId: string | null) => {
    if (!schedule) return;
    const dayDef = schedule.day_definitions.find((d) => d.date === date);
    if (!dayDef) return;
    const required = dayDef.type === 'open' ? 2 : 1;

    let shifts = [...(schedule.shifts || [])];
    let entry = shifts.find((s) => s.date === date);
    if (!entry) {
      entry = { date, type: dayDef.type, doctors: [] };
      shifts.push(entry);
    }
    let newDoctors = [...entry.doctors];
    if (doctorId === null) {
      newDoctors = [];
    } else if (newDoctors.includes(doctorId)) {
      newDoctors = newDoctors.filter((d) => d !== doctorId);
    } else {
      if (newDoctors.length >= required) {
        newDoctors = [...newDoctors.slice(0, required - 1), doctorId];
      } else {
        newDoctors.push(doctorId);
      }
    }
    shifts = shifts.map((s) => (s.date === date ? { ...s, doctors: newDoctors } : s));
    const newSched = { ...schedule, shifts };
    setSchedule(newSched);
    runValidation(shifts);
  };

  const handleAutoGenerate = async () => {
    if (!schedule) return;
    setSaving(true);
    try {
      const r = await api.post(`/schedules/${schedule.id}/generate`);
      setSchedule(r.data);
      runValidation(r.data.shifts);
    } catch (e) {
      Alert.alert('Αυτόματη δημιουργία', formatApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async (finalize: boolean) => {
    if (!schedule) return;
    setSaving(true);
    try {
      await api.put(`/schedules/${schedule.id}`, {
        shifts: schedule.shifts,
        status: finalize ? 'finalized' : 'draft',
      });
      Alert.alert('Επιτυχία', finalize ? 'Το πρόγραμμα οριστικοποιήθηκε' : 'Το πρόχειρο αποθηκεύτηκε');
      load();
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleExportPdf = async () => {
    if (!schedule) return;
    try {
      const token = await getAuthToken();
      const url = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api/schedules/${schedule.id}/export-pdf?token=${token}`;
      if (Platform.OS === 'web') {
        window.open(url, '_blank');
      } else {
        await Linking.openURL(url);
      }
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    }
  };

  if (loading || !schedule) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator size="large" color={Theme.colors.brand} />
      </SafeAreaView>
    );
  }

  const dayDefMap = Object.fromEntries(schedule.day_definitions.map((d) => [d.date, d]));
  const shiftMap = Object.fromEntries((schedule.shifts || []).map((s) => [s.date, s]));

  const first = new Date(schedule.year, schedule.month - 1, 1);
  const leading = first.getDay();
  const cells: (string | null)[] = [];
  for (let i = 0; i < leading; i++) cells.push(null);
  schedule.day_definitions.forEach((d) => cells.push(d.date));
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (string | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  const totalHard = validation?.hard.length || 0;
  const totalSoft = validation?.soft.length || 0;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={Theme.colors.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{GREEK_MONTHS[schedule.month]} {schedule.year}</Text>
          <Text style={styles.subtitle}>
            {schedule.status === 'finalized' ? 'Οριστικοποιημένο' : 'Πρόχειρο'} · {schedule.shifts.length} ημέρες
          </Text>
        </View>
        <TouchableOpacity onPress={() => setShowSummary(true)} style={styles.iconBtn}>
          <Ionicons name="stats-chart-outline" size={20} color={Theme.colors.textPrimary} />
        </TouchableOpacity>
      </View>

      {(totalHard > 0 || totalSoft > 0) && (
        <View
          style={[
            styles.banner,
            totalHard > 0 ? styles.bannerHard : styles.bannerSoft,
          ]}
        >
          <Ionicons
            name={totalHard > 0 ? 'close-circle' : 'warning'}
            size={18}
            color={totalHard > 0 ? Theme.colors.hardText : Theme.colors.softText}
          />
          <Text style={[styles.bannerText, { color: totalHard > 0 ? Theme.colors.hardText : Theme.colors.softText }]}>
            {totalHard > 0 ? `${totalHard} σκληρές παραβάσεις` : ''}
            {totalHard > 0 && totalSoft > 0 ? ' · ' : ''}
            {totalSoft > 0 ? `${totalSoft} προειδοποιήσεις` : ''}
          </Text>
        </View>
      )}
      {totalHard === 0 && totalSoft === 0 && validation && (
        <View style={[styles.banner, styles.bannerOk]}>
          <Ionicons name="checkmark-circle" size={18} color={Theme.colors.okText} />
          <Text style={[styles.bannerText, { color: Theme.colors.okText }]}>Όλοι οι κανόνες ικανοποιούνται</Text>
        </View>
      )}

      <ScrollView contentContainerStyle={{ padding: Theme.spacing.md, paddingBottom: 180 + insets.bottom }}>
        <View style={styles.weekRow}>
          {GREEK_DAYS_SHORT.map((dn) => (
            <Text key={dn} style={styles.weekHead}>{dn}</Text>
          ))}
        </View>
        {weeks.map((wk, wIdx) => (
          <View key={wIdx} style={{ flexDirection: 'row' }}>
            {wk.map((dateStr, cIdx) => {
              if (!dateStr) {
                return <View key={cIdx} style={[styles.cell, styles.cellEmpty]} />;
              }
              const dd = dayDefMap[dateStr];
              const sh = shiftMap[dateStr];
              const dayNum = parseInt(dateStr.slice(8), 10);
              const required = dd?.type === 'open' ? 2 : 1;
              const assigned = sh?.doctors || [];
              const isHoliday = !!holidays[dateStr] || !!dd?.is_holiday;
              const isWeekend = dd?.is_weekend;
              const v = validation?.per_day[dateStr];
              const hasHard = (v?.hard.length || 0) > 0;
              const hasSoft = (v?.soft.length || 0) > 0;

              const cellBg = hasHard
                ? Theme.colors.hardBg
                : hasSoft
                ? Theme.colors.softBg
                : isHoliday
                ? Theme.colors.softBg
                : isWeekend
                ? '#FEF2F2'
                : dd?.type === 'open'
                ? Theme.colors.pagniBg
                : Theme.colors.venizeleioBg;
              const borderColor = hasHard
                ? Theme.colors.hardBorder
                : hasSoft
                ? Theme.colors.softBorder
                : Theme.colors.border;

              return (
                <TouchableOpacity
                  key={cIdx}
                  onPress={() => setEditDay(dateStr)}
                  style={[styles.cell, { backgroundColor: cellBg, borderColor }]}
                  activeOpacity={0.7}
                  disabled={schedule.status === 'finalized'}
                >
                  <View style={styles.cellHead}>
                    <Text style={[styles.cellNum, isHoliday && { color: Theme.colors.softText }]}>{dayNum}</Text>
                    {hasHard && <Ionicons name="close-circle" size={12} color={Theme.colors.hardBorder} />}
                    {!hasHard && hasSoft && <Ionicons name="warning" size={11} color={Theme.colors.softBorder} />}
                  </View>
                  <View style={styles.cellNames}>
                    {assigned.length === 0 ? (
                      <Text style={styles.cellEmpty2}>—</Text>
                    ) : (
                      assigned.map((did) => (
                        <Text key={did} style={styles.cellName} numberOfLines={1}>
                          {(docMap[did] || '?').split(' ')[0]}
                        </Text>
                      ))
                    )}
                  </View>
                  {assigned.length < required && !hasHard && (
                    <View style={styles.cellMissing}>
                      <Text style={styles.cellMissingText}>+{required - assigned.length}</Text>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        ))}

        <View style={styles.legend}>
          <Text style={styles.legendEyebrow}>Υπόμνημα</Text>
          <View style={styles.legendRow}>
            <View style={[styles.legendDot, { backgroundColor: Theme.colors.pagniBg, borderColor: Theme.colors.pagniBorder, borderWidth: 1 }]} />
            <Text style={styles.legendText}>Α = Ανοιχτή (ΠΑΓΝΗ, 2 γιατροί)</Text>
          </View>
          <View style={styles.legendRow}>
            <View style={[styles.legendDot, { backgroundColor: Theme.colors.venizeleioBg, borderColor: Theme.colors.venizeleioBorder, borderWidth: 1 }]} />
            <Text style={styles.legendText}>Κ = Κλειστή (ΒΕΝΙΖΕΛΕΙΟ, 1 γιατρός)</Text>
          </View>
          <View style={styles.legendRow}>
            <View style={[styles.legendDot, { backgroundColor: Theme.colors.softBg, borderColor: Theme.colors.softBorder, borderWidth: 1 }]} />
            <Text style={styles.legendText}>Αργία / Προειδοποίηση</Text>
          </View>
          <View style={styles.legendRow}>
            <View style={[styles.legendDot, { backgroundColor: Theme.colors.hardBg, borderColor: Theme.colors.hardBorder, borderWidth: 1 }]} />
            <Text style={styles.legendText}>Σκληρή Παράβαση</Text>
          </View>
        </View>
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: Theme.spacing.md + insets.bottom }]}>
        <View style={styles.footerRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnGhost, saving && { opacity: 0.6 }]}
            onPress={handleAutoGenerate}
            disabled={saving || schedule.status === 'finalized'}
          >
            <Ionicons name="sparkles" size={16} color={Theme.colors.textPrimary} />
            <Text style={styles.btnGhostText}>Αυτόματη</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnGhost]}
            onPress={handleExportPdf}
          >
            <Ionicons name="document-text-outline" size={16} color={Theme.colors.textPrimary} />
            <Text style={styles.btnGhostText}>PDF</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.footerRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnGhost, saving && { opacity: 0.6 }]}
            onPress={() => handleSave(false)}
            disabled={saving || schedule.status === 'finalized'}
          >
            <Text style={styles.btnGhostText}>Αποθήκευση</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnPrimary, saving && { opacity: 0.6 }]}
            onPress={() => handleSave(true)}
            disabled={saving || schedule.status === 'finalized'}
          >
            {saving ? (
              <ActivityIndicator size="small" color={Theme.colors.textInverse} />
            ) : (
              <>
                <Ionicons name="checkmark-circle" size={16} color={Theme.colors.textInverse} />
                <Text style={styles.btnPrimaryText}>Οριστικοποίηση</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </View>

      <Modal visible={!!editDay} transparent animationType="slide" onRequestClose={() => setEditDay(null)}>
        <View style={{ flex: 1, justifyContent: 'flex-end' }}>
          <TouchableOpacity activeOpacity={1} style={styles.modalBackdrop} onPress={() => setEditDay(null)} />
          <View style={styles.sheet}>
            <View style={styles.modalHandle} />
            {editDay && (() => {
              const dd = dayDefMap[editDay];
              const sh = shiftMap[editDay];
              const required = dd?.type === 'open' ? 2 : 1;
              const assigned = sh?.doctors || [];
              const dt = new Date(editDay);
              const dayName = GREEK_DAYS_LONG[dt.getDay()];
              const v = validation?.per_day[editDay];
              return (
                <>
                  <Text style={styles.sheetTitle}>
                    {dayName}, {dt.getDate()} {GREEK_MONTHS[schedule.month]}
                  </Text>
                  <Text style={styles.sheetSub}>
                    {dd?.type === 'open' ? 'Ανοιχτή Εφημερία (ΠΑΓΝΗ)' : 'Κλειστή Εφημερία (ΒΕΝΙΖΕΛΕΙΟ)'} · {required} γιατρ{required === 1 ? 'ός' : 'οί'}
                    {holidays[editDay] ? ` · ${holidays[editDay]}` : dd?.is_holiday ? ' · Αργία' : ''}
                  </Text>
                  {v?.hard.length ? (
                    <View style={[styles.alert, styles.alertHard]}>
                      {v.hard.map((h: any, idx: number) => (
                        <Text key={idx} style={styles.alertHardText}>• {h.msg}</Text>
                      ))}
                    </View>
                  ) : null}
                  {v?.soft.length ? (
                    <View style={[styles.alert, styles.alertSoft]}>
                      {v.soft.map((h: any, idx: number) => (
                        <Text key={idx} style={styles.alertSoftText}>• {h.msg}</Text>
                      ))}
                    </View>
                  ) : null}
                  <ScrollView style={{ maxHeight: 320 }}>
                    {doctors.map((doc) => {
                      const isAssigned = assigned.includes(doc.id);
                      return (
                        <TouchableOpacity
                          key={doc.id}
                          onPress={() => handleAssignDoctor(editDay, doc.id)}
                          style={[styles.docOption, isAssigned && styles.docOptionActive]}
                          activeOpacity={0.7}
                        >
                          <View style={[styles.docCheck, isAssigned && styles.docCheckActive]}>
                            {isAssigned && <Ionicons name="checkmark" size={14} color={Theme.colors.textInverse} />}
                          </View>
                          <Text style={[styles.docOptionName, isAssigned && { fontWeight: '700' }]}>{doc.full_name}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </ScrollView>
                  <View style={styles.sheetActions}>
                    <TouchableOpacity
                      style={[styles.btn, styles.btnGhost, { flex: 1 }]}
                      onPress={() => handleAssignDoctor(editDay, null)}
                    >
                      <Text style={styles.btnGhostText}>Καθαρισμός</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.btn, styles.btnPrimary, { flex: 1 }]}
                      onPress={() => setEditDay(null)}
                    >
                      <Text style={styles.btnPrimaryText}>Κλείσιμο</Text>
                    </TouchableOpacity>
                  </View>
                </>
              );
            })()}
          </View>
        </View>
      </Modal>

      <Modal visible={showSummary} transparent animationType="slide" onRequestClose={() => setShowSummary(false)}>
        <View style={{ flex: 1, justifyContent: 'flex-end' }}>
          <TouchableOpacity activeOpacity={1} style={styles.modalBackdrop} onPress={() => setShowSummary(false)} />
          <View style={styles.sheet}>
            <View style={styles.modalHandle} />
            <Text style={styles.sheetTitle}>Σύνοψη Εφημεριών</Text>
            <Text style={styles.sheetSub}>{GREEK_MONTHS[schedule.month]} {schedule.year}</Text>
            <ScrollView style={{ maxHeight: 400, marginTop: 8 }}>
              {validation && Object.entries(validation.per_doctor).map(([did, stats]) => (
                <View key={did} style={styles.statRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.statName}>{stats.name}</Text>
                    <Text style={styles.statSub}>
                      Σ/Κ: {stats.weekends} · Αργίες: {stats.holidays}
                    </Text>
                  </View>
                  <Text style={styles.statBig}>{stats.shifts}</Text>
                </View>
              ))}
              {validation?.soft.length ? (
                <View style={[styles.alert, styles.alertSoft]}>
                  <Text style={[styles.alertEyebrow, { color: Theme.colors.softText }]}>Προειδοποιήσεις</Text>
                  {validation.soft.map((s: any, idx: number) => (
                    <Text key={idx} style={styles.alertSoftText}>• {s.msg}</Text>
                  ))}
                </View>
              ) : null}
              {validation?.hard.length ? (
                <View style={[styles.alert, styles.alertHard]}>
                  <Text style={[styles.alertEyebrow, { color: Theme.colors.hardText }]}>Σκληρές Παραβάσεις</Text>
                  {validation.hard.map((s: any, idx: number) => (
                    <Text key={idx} style={styles.alertHardText}>• {s.msg}</Text>
                  ))}
                </View>
              ) : null}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Theme.colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: Theme.spacing.md, paddingTop: Theme.spacing.sm, gap: 12,
    paddingBottom: Theme.spacing.sm, borderBottomWidth: 1, borderBottomColor: Theme.colors.border,
  },
  title: { fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary },
  subtitle: { fontSize: 11, color: Theme.colors.textSecondary, marginTop: 2 },
  iconBtn: {
    width: 40, height: 40, borderRadius: Theme.radius.md,
    borderWidth: 1, borderColor: Theme.colors.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.surface,
  },
  banner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 10, paddingHorizontal: Theme.spacing.md,
    borderBottomWidth: 1,
  },
  bannerHard: { backgroundColor: Theme.colors.hardBg, borderBottomColor: Theme.colors.hardBorder },
  bannerSoft: { backgroundColor: Theme.colors.softBg, borderBottomColor: Theme.colors.softBorder },
  bannerOk: { backgroundColor: Theme.colors.okBg, borderBottomColor: Theme.colors.okBorder },
  bannerText: { fontSize: 13, fontWeight: '600' },
  weekRow: { flexDirection: 'row', marginBottom: 4 },
  weekHead: { flex: 1, fontSize: 10, fontWeight: '700', color: Theme.colors.textSecondary, letterSpacing: 1, textAlign: 'center', textTransform: 'uppercase' },
  cell: {
    flex: 1, minHeight: 86, borderWidth: 1, margin: 1, borderRadius: 6,
    padding: 4, position: 'relative',
  },
  cellEmpty: { backgroundColor: 'transparent', borderColor: 'transparent' },
  cellHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cellNum: { fontSize: 13, fontWeight: '700', color: Theme.colors.textPrimary },
  cellType: { fontSize: 9, fontWeight: '700', marginTop: 1 },
  cellNames: { marginTop: 2, gap: 1 },
  cellName: { fontSize: 9, color: Theme.colors.textPrimary, fontWeight: '600' },
  cellEmpty2: { fontSize: 11, color: Theme.colors.textDisabled },
  cellMissing: {
    position: 'absolute', bottom: 2, right: 2,
    backgroundColor: Theme.colors.softBg, paddingHorizontal: 4, borderRadius: 3,
  },
  cellMissingText: { fontSize: 9, color: Theme.colors.softText, fontWeight: '700' },
  legend: {
    marginTop: Theme.spacing.lg, padding: Theme.spacing.md,
    backgroundColor: Theme.colors.surface, borderWidth: 1, borderColor: Theme.colors.border, borderRadius: Theme.radius.md,
    gap: 6,
  },
  legendEyebrow: { fontSize: 10, fontWeight: '700', color: Theme.colors.textSecondary, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 4 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  legendDot: { width: 14, height: 14, borderRadius: 3 },
  legendText: { fontSize: 12, color: Theme.colors.textSecondary },
  footer: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    backgroundColor: Theme.colors.surface, padding: Theme.spacing.md,
    borderTopWidth: 1, borderTopColor: Theme.colors.border, gap: 8,
  },
  footerRow: { flexDirection: 'row', gap: 8 },
  btn: { flex: 1, flexDirection: 'row', paddingVertical: 12, borderRadius: Theme.radius.md, alignItems: 'center', justifyContent: 'center', gap: 6 },
  btnGhost: { borderWidth: 1, borderColor: Theme.colors.border, backgroundColor: Theme.colors.surface },
  btnGhostText: { color: Theme.colors.textPrimary, fontWeight: '600', fontSize: 13 },
  btnPrimary: { backgroundColor: Theme.colors.brand },
  btnPrimaryText: { color: Theme.colors.textInverse, fontWeight: '700', fontSize: 13 },
  modalBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: Theme.colors.overlay },
  sheet: {
    backgroundColor: Theme.colors.surface, padding: Theme.spacing.lg, paddingBottom: Theme.spacing.xl,
    borderTopLeftRadius: Theme.radius.lg, borderTopRightRadius: Theme.radius.lg,
  },
  modalHandle: { width: 40, height: 4, backgroundColor: Theme.colors.border, borderRadius: 2, alignSelf: 'center', marginBottom: Theme.spacing.md },
  sheetTitle: { fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary },
  sheetSub: { fontSize: 12, color: Theme.colors.textSecondary, marginTop: 4, marginBottom: Theme.spacing.md },
  alert: { padding: 10, borderRadius: Theme.radius.sm, marginBottom: Theme.spacing.sm, borderWidth: 1 },
  alertHard: { backgroundColor: Theme.colors.hardBg, borderColor: Theme.colors.hardBorder },
  alertSoft: { backgroundColor: Theme.colors.softBg, borderColor: Theme.colors.softBorder },
  alertHardText: { fontSize: 12, color: Theme.colors.hardText, marginVertical: 1 },
  alertSoftText: { fontSize: 12, color: Theme.colors.softText, marginVertical: 1 },
  alertEyebrow: { fontSize: 10, fontWeight: '700', letterSpacing: 1.2, textTransform: 'uppercase', marginBottom: 4 },
  docOption: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: Theme.colors.border,
  },
  docOptionActive: {},
  docCheck: {
    width: 22, height: 22, borderRadius: 4, borderWidth: 1.5, borderColor: Theme.colors.border,
    alignItems: 'center', justifyContent: 'center',
  },
  docCheckActive: { backgroundColor: Theme.colors.brand, borderColor: Theme.colors.brand },
  docOptionName: { fontSize: 14, color: Theme.colors.textPrimary, flex: 1 },
  sheetActions: { flexDirection: 'row', gap: 10, marginTop: Theme.spacing.md },
  statRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: Theme.colors.border, gap: 12,
  },
  statName: { fontSize: 14, fontWeight: '600', color: Theme.colors.textPrimary },
  statSub: { fontSize: 11, color: Theme.colors.textSecondary, marginTop: 2 },
  statBig: { fontSize: 24, fontWeight: '700', color: Theme.colors.textPrimary },
});
