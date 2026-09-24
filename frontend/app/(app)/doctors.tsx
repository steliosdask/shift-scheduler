import { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  TextInput,
  Modal,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
  Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Theme } from '../../constants/Theme';
import { api, formatApiError } from '../../lib/api';
import { confirmAction } from '../../lib/confirm';

type Doctor = {
  id: string;
  full_name: string;
  notes?: string;
  is_active: boolean;
};

export default function DoctorsScreen() {
  const router = useRouter();
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Doctor | null>(null);
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [active, setActive] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get('/doctors');
      setDoctors(r.data);
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const openAdd = () => {
    setEditing(null);
    setName('');
    setNotes('');
    setActive(true);
    setModalOpen(true);
  };

  const openEdit = (d: Doctor) => {
    setEditing(d);
    setName(d.full_name);
    setNotes(d.notes || '');
    setActive(d.is_active);
    setModalOpen(true);
  };

  const onSave = async () => {
    if (!name.trim()) {
      Alert.alert('Προσοχή', 'Παρακαλώ εισάγετε όνομα γιατρού');
      return;
    }
    setSaving(true);
    try {
      const payload = { full_name: name.trim(), notes: notes.trim(), is_active: active };
      if (editing) {
        await api.put(`/doctors/${editing.id}`, payload);
      } else {
        await api.post('/doctors', payload);
      }
      setModalOpen(false);
      load();
    } catch (e) {
      Alert.alert('Σφάλμα', formatApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (d: Doctor) => {
    const ok = await confirmAction('Διαγραφή Γιατρού', `Διαγραφή του/της "${d.full_name}";`, {
      confirmText: 'Διαγραφή',
      destructive: true,
    });
    if (!ok) return;
    try {
      await api.delete(`/doctors/${d.id}`);
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
        <TouchableOpacity onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={Theme.colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.title}>Διαχείριση Γιατρών</Text>
        <TouchableOpacity onPress={openAdd} style={[styles.iconBtn, styles.iconBtnPrimary]}>
          <Ionicons name="add" size={22} color={Theme.colors.textInverse} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={doctors}
        keyExtractor={(d) => d.id}
        contentContainerStyle={{ padding: Theme.spacing.md }}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="people-outline" size={48} color={Theme.colors.textDisabled} />
            <Text style={styles.emptyText}>Δεν υπάρχουν γιατροί</Text>
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={[styles.avatar, !item.is_active && { opacity: 0.4 }]}>
              <Text style={styles.avatarText}>
                {item.full_name.split(' ').map((p) => p[0]).slice(0, 2).join('')}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[styles.rowName, !item.is_active && styles.rowNameInactive]}>
                {item.full_name}
              </Text>
              <View style={styles.rowMeta}>
                <View style={[styles.badge, item.is_active ? styles.badgeOk : styles.badgeOff]}>
                  <Text style={[styles.badgeText, item.is_active ? styles.badgeTextOk : styles.badgeTextOff]}>
                    {item.is_active ? 'Ενεργός' : 'Ανενεργός'}
                  </Text>
                </View>
                {item.notes ? <Text style={styles.rowNotes}>{item.notes}</Text> : null}
              </View>
            </View>
            <TouchableOpacity
              onPress={() => openEdit(item)}
              style={styles.smallBtn}
              hitSlop={8}
            >
              <Ionicons name="create-outline" size={18} color={Theme.colors.textPrimary} />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => onDelete(item)}
              style={styles.smallBtn}
              hitSlop={8}
            >
              <Ionicons name="trash-outline" size={18} color={Theme.colors.hardText} />
            </TouchableOpacity>
          </View>
        )}
      />

      <Modal visible={modalOpen} transparent animationType="slide" onRequestClose={() => setModalOpen(false)}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalRoot}
        >
          <TouchableOpacity activeOpacity={1} style={styles.modalBackdrop} onPress={() => setModalOpen(false)} />
          <View style={styles.modalSheet}>
            <View style={styles.modalHandle} />
            <Text style={styles.modalTitle}>{editing ? 'Επεξεργασία Γιατρού' : 'Νέος Γιατρός'}</Text>
            <Text style={styles.label}>Ονοματεπώνυμο</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="π.χ. Παπαδόπουλος Γεώργιος"
              placeholderTextColor={Theme.colors.textDisabled}
            />
            <Text style={styles.label}>Σημειώσεις (προαιρετικό)</Text>
            <TextInput
              style={[styles.input, { minHeight: 60 }]}
              value={notes}
              onChangeText={setNotes}
              placeholder="ειδικότητα, σημειώσεις..."
              placeholderTextColor={Theme.colors.textDisabled}
              multiline
            />
            <View style={styles.toggleRow}>
              <Text style={styles.toggleLabel}>Ενεργός</Text>
              <Switch
                value={active}
                onValueChange={setActive}
                trackColor={{ false: Theme.colors.border, true: Theme.colors.brand }}
              />
            </View>
            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.btn, styles.btnGhost]}
                onPress={() => setModalOpen(false)}
                disabled={saving}
              >
                <Text style={styles.btnGhostText}>Άκυρο</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.btnPrimary, saving && { opacity: 0.6 }]}
                onPress={onSave}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator color={Theme.colors.textInverse} size="small" />
                ) : (
                  <Text style={styles.btnPrimaryText}>{editing ? 'Αποθήκευση' : 'Προσθήκη'}</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
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
    gap: 12,
  },
  title: { flex: 1, fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary, textAlign: 'center' },
  iconBtn: {
    width: 40, height: 40, borderRadius: Theme.radius.md,
    borderWidth: 1, borderColor: Theme.colors.border,
    alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.surface,
  },
  iconBtnPrimary: { backgroundColor: Theme.colors.brand, borderColor: Theme.colors.brand },
  empty: { alignItems: 'center', padding: Theme.spacing.xl, gap: 8 },
  emptyText: { fontSize: 16, color: Theme.colors.textSecondary, fontWeight: '600' },
  row: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 14, gap: 12,
    borderBottomWidth: 1, borderBottomColor: Theme.colors.border,
  },
  avatar: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: Theme.colors.surfaceRaised, alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontSize: 13, fontWeight: '700', color: Theme.colors.textPrimary },
  rowName: { fontSize: 15, fontWeight: '600', color: Theme.colors.textPrimary },
  rowNameInactive: { color: Theme.colors.textDisabled, textDecorationLine: 'line-through' },
  rowMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' },
  rowNotes: { fontSize: 12, color: Theme.colors.textSecondary, flex: 1 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, borderWidth: 1 },
  badgeOk: { backgroundColor: Theme.colors.okBg, borderColor: Theme.colors.okBorder },
  badgeOff: { backgroundColor: Theme.colors.surfaceRaised, borderColor: Theme.colors.border },
  badgeText: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  badgeTextOk: { color: Theme.colors.okText },
  badgeTextOff: { color: Theme.colors.textSecondary },
  smallBtn: { padding: 8, borderRadius: Theme.radius.sm },
  modalRoot: { flex: 1, justifyContent: 'flex-end' },
  modalBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: Theme.colors.overlay },
  modalSheet: {
    backgroundColor: Theme.colors.surface, padding: Theme.spacing.lg, paddingBottom: Theme.spacing.xl,
    borderTopLeftRadius: Theme.radius.lg, borderTopRightRadius: Theme.radius.lg,
  },
  modalHandle: {
    width: 40, height: 4, backgroundColor: Theme.colors.border, borderRadius: 2,
    alignSelf: 'center', marginBottom: Theme.spacing.md,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: Theme.colors.textPrimary, marginBottom: Theme.spacing.md },
  label: { fontSize: 12, fontWeight: '600', color: Theme.colors.textSecondary, marginTop: Theme.spacing.sm, marginBottom: 6 },
  input: {
    borderWidth: 1, borderColor: Theme.colors.border, borderRadius: Theme.radius.sm,
    padding: 12, fontSize: 15, color: Theme.colors.textPrimary, backgroundColor: Theme.colors.surface,
  },
  toggleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: Theme.spacing.md },
  toggleLabel: { fontSize: 14, color: Theme.colors.textPrimary, fontWeight: '600' },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: Theme.spacing.lg },
  btn: { flex: 1, paddingVertical: 14, borderRadius: Theme.radius.md, alignItems: 'center', justifyContent: 'center' },
  btnGhost: { borderWidth: 1, borderColor: Theme.colors.border },
  btnGhostText: { color: Theme.colors.textPrimary, fontWeight: '700', fontSize: 14 },
  btnPrimary: { backgroundColor: Theme.colors.brand },
  btnPrimaryText: { color: Theme.colors.textInverse, fontWeight: '700', fontSize: 14 },
});
