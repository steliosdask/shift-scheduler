import { Stack, Redirect } from 'expo-router';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useAuth } from '../../lib/auth';
import { Theme } from '../../constants/Theme';

export default function AppLayout() {
  const { user } = useAuth();
  if (user === undefined) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Theme.colors.brand} />
      </View>
    );
  }
  if (!user) return <Redirect href="/login" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.bg },
});
