import { Alert, Platform } from 'react-native';

/**
 * Cross-platform confirmation dialog.
 * - On web: uses native window.confirm (Alert.alert ignores buttons on web)
 * - On native (iOS/Android): uses Alert.alert with proper button callbacks
 *
 * Returns a Promise<boolean>: true if the user confirmed, false otherwise.
 *
 * Usage:
 *   const ok = await confirmAction('Διαγραφή', 'Σίγουρα;');
 *   if (!ok) return;
 *   await api.delete(...);
 */
export function confirmAction(
  title: string,
  message: string,
  options: {
    confirmText?: string;
    cancelText?: string;
    destructive?: boolean;
  } = {}
): Promise<boolean> {
  const {
    confirmText = 'OK',
    cancelText = 'Άκυρο',
    destructive = false,
  } = options;

  if (Platform.OS === 'web') {
    // window.confirm shows title + message in a single string; we join them.
    const text = message ? `${title}\n\n${message}` : title;
    return Promise.resolve(window.confirm(text));
  }

  return new Promise((resolve) => {
    Alert.alert(title, message, [
      {
        text: cancelText,
        style: 'cancel',
        onPress: () => resolve(false),
      },
      {
        text: confirmText,
        style: destructive ? 'destructive' : 'default',
        onPress: () => resolve(true),
      },
    ]);
  });
}