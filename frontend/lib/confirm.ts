import { Alert, Platform } from 'react-native';

/** Confirmation dialog that also works on web, where Alert.alert ignores buttons. */
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
