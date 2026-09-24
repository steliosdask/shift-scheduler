import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuth } from '../lib/auth';
import { Theme } from '../constants/Theme';
import { formatApiError } from '../lib/api';

export default function Login() {
  const { login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async () => {
    setError('');
    setLoading(true);
    try {
      await login(username.trim(), password);
      router.replace('/(app)/dashboard');
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={{ flex: 1 }}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.brand}>
            <View style={styles.logo}>
              <Ionicons name="medical" size={28} color={Theme.colors.textInverse} />
            </View>
            <Text style={styles.appTitle}>Πρόγραμμα Εφημεριών</Text>
            <Text style={styles.appSub}>ΠΑΓΝΗ — ΒΕΝΙΖΕΛΕΙΟ</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.h2}>Σύνδεση Χρήστη</Text>
            <Text style={styles.label}>Όνομα χρήστη</Text>
            <TextInput
              testID="login-username-input"
              style={styles.input}
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor={Theme.colors.textDisabled}
            />
            <Text style={styles.label}>Κωδικός</Text>
            <TextInput
              testID="login-password-input"
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder="••••••••"
              placeholderTextColor={Theme.colors.textDisabled}
            />
            {error ? (
              <View style={styles.errorBox} testID="login-error">
                <Ionicons name="alert-circle" size={16} color={Theme.colors.hardText} />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}
            <TouchableOpacity
              testID="login-submit-btn"
              style={[styles.cta, loading && { opacity: 0.6 }]}
              onPress={onSubmit}
              disabled={loading}
              activeOpacity={0.85}
            >
              {loading ? (
                <ActivityIndicator color={Theme.colors.textInverse} />
              ) : (
                <Text style={styles.ctaText}>Σύνδεση</Text>
              )}
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Theme.colors.bg },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: Theme.spacing.lg },
  brand: { alignItems: 'center', marginBottom: Theme.spacing.xl },
  logo: {
    width: 56,
    height: 56,
    borderRadius: Theme.radius.md,
    backgroundColor: Theme.colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Theme.spacing.md,
  },
  appTitle: { fontSize: 22, fontWeight: '700', color: Theme.colors.textPrimary, letterSpacing: -0.3 },
  appSub: {
    fontSize: 11,
    fontWeight: '700',
    color: Theme.colors.textSecondary,
    letterSpacing: 2,
    marginTop: 4,
    textTransform: 'uppercase',
  },
  card: {
    backgroundColor: Theme.colors.surface,
    borderWidth: 1,
    borderColor: Theme.colors.border,
    borderRadius: Theme.radius.lg,
    padding: Theme.spacing.lg,
    maxWidth: 480,
    width: '100%',
    alignSelf: 'center',
  },
  h2: { fontSize: 20, fontWeight: '700', color: Theme.colors.textPrimary, marginBottom: Theme.spacing.lg },
  label: { fontSize: 12, fontWeight: '600', color: Theme.colors.textSecondary, marginBottom: 6, marginTop: Theme.spacing.sm },
  input: {
    borderBottomWidth: 1.5,
    borderBottomColor: Theme.colors.border,
    paddingVertical: 10,
    fontSize: 16,
    color: Theme.colors.textPrimary,
    marginBottom: 4,
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: Theme.colors.hardBg,
    borderColor: Theme.colors.hardBorder,
    borderWidth: 1,
    borderRadius: Theme.radius.sm,
    padding: 10,
    marginTop: Theme.spacing.md,
  },
  errorText: { color: Theme.colors.hardText, fontSize: 13, flex: 1 },
  cta: {
    backgroundColor: Theme.colors.brand,
    borderRadius: Theme.radius.md,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: Theme.spacing.lg,
  },
  ctaText: { color: Theme.colors.textInverse, fontSize: 16, fontWeight: '700', letterSpacing: 0.3 },
});
