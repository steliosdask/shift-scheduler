import { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Modal,
  ScrollView,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Theme, GREEK_MONTHS } from '../../constants/Theme';
import { api, formatApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { confirmAction } from '../../lib/confirm';
import { SCHEDULE_RULES } from '../../constants/rules';

type Schedule = {
  id: string;
  year: number;
  month: number;
  status: string;
  updated_at: string;
  shifts: any[];
};

export default function Dashboard() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [doctorsCount, setDoctorsCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showRules, setShowRules] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([api.get('/schedules'), api.get('/doctors')]);
      setSchedules(s.data);
      setDoctorsCount(d.data.length);
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onDelete = async (id: string) => {
    const ok = await confirmAction(
      'Διαγραφή Προγράμματος',
      'Σίγουρα θέλετε να διαγράψετε αυτό το πρόγραμμα;',
      { confirmText: 'Διαγραφή', destructive: true }
    );
    if (!ok) return;
    try {
      await api.delete(`/schedules/${id}`);
      load();
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    }
  };

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
        <View style={{ flex: 1 }}>
          <Text style={styles.eyebrow}>Καλώς ήρθατε</Text>
          <Text style={styles.title}>{user?.username}</Text>
        </View>
        <TouchableOpacity onPress={() => setShowRules(true)} style={[styles.iconBtn, { marginRight: 8 }]}>
          <Ionicons name="information-circle-outline" size={22} color={Theme.colors.textPrimary} />
        </TouchableOpacity>
        <TouchableOpacity onPress={logout} style={styles.iconBtn}>
          <Ionicons name="log-out-outline" size={22} color={Theme.colors.textPrimary} />
        </TouchableOpacity>
      </View>

      <Modal visible={showRules} transparent animationType="slide" onRequestClose={() => setShowRules(false)}>
        <View style={{ flex: 1, justifyContent: 'flex-end' }}>
          <TouchableOpacity activeOpacity={1} style={styles.modalBackdrop} onPress={() => setShowRules(false)} />
          <View style={styles.sheet}>
            <View style={styles.modalHandle} />
            <Text style={styles.sheetTitle}>Κανόνες Προγράμματος</Text>
            <ScrollView style={{ maxHeight: 460, marginTop: Theme.spacing.sm }}>
              {SCHEDULE_RULES.map((section) => (
                <View key={section.title} style={{ marginBottom: Theme.spacing.md }}>
                  <Text style={styles.rulesHeading}>{section.title}</Text>
                  {section.items.map((item) => (
                    <View key={item} style={styles.ruleRow}>
                      <Text style={styles.ruleBullet}>•</Text>
                      <Text style={styles.ruleText}>{item}</Text>
                    </View>
                  ))}
                </View>
              ))}
            </ScrollView>
            <TouchableOpacity style={styles.sheetClose} onPress={() => setShowRules(false)} activeOpacity={0.85}>
              <Text style={styles.ctaText}>Κλείσιμο</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>{schedules.length}</Text>
          <Text style={styles.statLabel}>Προγράμματα</Text>
        </View>
        <TouchableOpacity
          style={styles.statCard}
          onPress={() => router.push('/(app)/doctors')}
          activeOpacity={0.7}
        >
          <Text style={styles.statValue}>{doctorsCount}</Text>
          <Text style={styles.statLabel}>Γιατροί</Text>
          <View style={styles.statArrow}>
            <Ionicons name="chevron-forward" size={14} color={Theme.colors.textSecondary} />
          </View>
        </TouchableOpacity>
      </View>

      <TouchableOpacity
        style={styles.cta}
        onPress={() => router.push('/(app)/wizard')}
        activeOpacity={0.85}
      >
        <Ionicons name="add-circle-outline" size={22} color={Theme.colors.textInverse} />
        <Text style={styles.ctaText}>Νέο Πρόγραμμα Εφημεριών</Text>
      </TouchableOpacity>

      <Text style={styles.sectionTitle}>Πρόσφατα Προγράμματα</Text>

      <FlatList
        data={schedules}
        keyExtractor={(it) => it.id}
        contentContainerStyle={{ padding: Theme.spacing.md, paddingTop: 0, paddingBottom: Theme.spacing.md + insets.bottom }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="calendar-outline" size={48} color={Theme.colors.textDisabled} />
            <Text style={styles.emptyText}>Δεν υπάρχουν προγράμματα ακόμη</Text>
            <Text style={styles.emptyHint}>Πατήστε «Νέο Πρόγραμμα Εφημεριών» για να ξεκινήσετε</Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => router.push(`/(app)/schedule/${item.id}`)}
            activeOpacity={0.7}
          >
            <View style={styles.rowMonth}>
              <Text style={styles.rowMonthDay}>{GREEK_MONTHS[item.month].slice(0, 3)}</Text>
              <Text style={styles.rowMonthYear}>{item.year}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>
                {GREEK_MONTHS[item.month]} {item.year}
              </Text>
              <View style={styles.rowMeta}>
                <View
                  style={[
                    styles.badge,
                    item.status === 'finalized' ? styles.badgeOk : styles.badgeDraft,
                  ]}
                >
                  <Text
                    style={[
                      styles.badgeText,
                      item.status === 'finalized' ? styles.badgeTextOk : styles.badgeTextDraft,
                    ]}
                  >
                    {item.status === 'finalized' ? 'Οριστικοποιημένο' : 'Πρόχειρο'}
                  </Text>
                </View>
                <Text style={styles.rowSub}>
                  {(item.shifts || []).length} ημέρες
                </Text>
              </View>
            </View>
            <TouchableOpacity
              hitSlop={10}
              onPress={() => onDelete(item.id)}
              style={{ padding: 6 }}
            >
              <Ionicons name="trash-outline" size={18} color={Theme.colors.textDisabled} />
            </TouchableOpacity>
            <Ionicons name="chevron-forward" size={18} color={Theme.colors.textDisabled} />
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Theme.colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Theme.spacing.md,
    paddingTop: Theme.spacing.md,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: '600',
    color: Theme.colors.textSecondary,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
  title: { fontSize: 22, fontWeight: '700', color: Theme.colors.textPrimary, marginTop: 2 },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: Theme.radius.md,
    borderWidth: 1,
    borderColor: Theme.colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statsRow: { flexDirection: 'row', gap: 12, padding: Theme.spacing.md },
  statCard: {
    flex: 1,
    borderWidth: 1,
    borderColor: Theme.colors.border,
    borderRadius: Theme.radius.md,
    padding: Theme.spacing.md,
    backgroundColor: Theme.colors.surface,
    position: 'relative',
  },
  statValue: { fontSize: 28, fontWeight: '700', color: Theme.colors.textPrimary },
  statLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: Theme.colors.textSecondary,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginTop: 4,
  },
  statArrow: { position: 'absolute', top: 12, right: 12 },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: Theme.colors.brand,
    marginHorizontal: Theme.spacing.md,
    paddingVertical: 16,
    borderRadius: Theme.radius.md,
  },
  ctaText: { color: Theme.colors.textInverse, fontSize: 15, fontWeight: '700', letterSpacing: 0.3 },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: Theme.colors.textSecondary,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    paddingHorizontal: Theme.spacing.md,
    marginTop: Theme.spacing.lg,
    marginBottom: Theme.spacing.sm,
  },
  empty: { alignItems: 'center', padding: Theme.spacing.xl, gap: 8 },
  emptyText: { fontSize: 16, color: Theme.colors.textSecondary, fontWeight: '600' },
  emptyHint: { fontSize: 13, color: Theme.colors.textDisabled, textAlign: 'center' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: Theme.spacing.sm,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: Theme.colors.border,
  },
  rowMonth: {
    width: 56,
    height: 56,
    borderRadius: Theme.radius.md,
    backgroundColor: Theme.colors.surfaceRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowMonthDay: { fontSize: 12, fontWeight: '700', color: Theme.colors.textPrimary, textTransform: 'uppercase' },
  rowMonthYear: { fontSize: 12, color: Theme.colors.textSecondary, marginTop: 2 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: Theme.colors.textPrimary },
  rowMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  rowSub: { fontSize: 12, color: Theme.colors.textSecondary },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, borderWidth: 1 },
  badgeOk: { backgroundColor: Theme.colors.okBg, borderColor: Theme.colors.okBorder },
  badgeDraft: { backgroundColor: Theme.colors.surfaceRaised, borderColor: Theme.colors.border },
  badgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  badgeTextOk: { color: Theme.colors.okText },
  badgeTextDraft: { color: Theme.colors.textSecondary },
  modalBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: Theme.colors.overlay },
  sheet: {
    backgroundColor: Theme.colors.surface,
    padding: Theme.spacing.lg,
    paddingBottom: Theme.spacing.xl,
    borderTopLeftRadius: Theme.radius.lg,
    borderTopRightRadius: Theme.radius.lg,
  },
  modalHandle: {
    width: 40,
    height: 4,
    backgroundColor: Theme.colors.border,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: Theme.spacing.md,
  },
  sheetTitle: { fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary },
  rulesHeading: {
    fontSize: 11,
    fontWeight: '700',
    color: Theme.colors.textSecondary,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  ruleRow: { flexDirection: 'row', gap: 8, marginBottom: 6 },
  ruleBullet: { fontSize: 14, color: Theme.colors.textSecondary, lineHeight: 20 },
  ruleText: { flex: 1, fontSize: 14, color: Theme.colors.textPrimary, lineHeight: 20 },
  sheetClose: {
    backgroundColor: Theme.colors.brand,
    borderRadius: Theme.radius.md,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: Theme.spacing.sm,
  },
});
