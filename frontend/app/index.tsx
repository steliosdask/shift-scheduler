import { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { Redirect } from 'expo-router';
import { useAuth } from '../lib/auth';
import { Theme } from '../constants/Theme';

export default function Index() {
  const { user } = useAuth();

  if (user === undefined) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Theme.colors.brand} />
      </View>
    );
  }
  if (!user) return <Redirect href="/login" />;
  return <Redirect href="/(app)/dashboard" />;
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Theme.colors.bg },
});
