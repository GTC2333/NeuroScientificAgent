// frontend/src/components/Notification.tsx
import { useState, useEffect } from 'react';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

interface Notification {
  id: string;
  type: NotificationType;
  message: string;
}

let notificationCallback: ((notification: Omit<Notification, 'id'>) => void) | null = null;

export function showNotification(type: NotificationType, message: string) {
  if (notificationCallback) {
    notificationCallback({ type, message });
  }
}

export function NotificationContainer() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    notificationCallback = (notification) => {
      const id = Math.random().toString(36).substr(2, 9);
      setNotifications((prev) => [...prev, { ...notification, id }]);

      // Auto dismiss after 5 seconds
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
      }, 5000);
    };

    return () => {
      notificationCallback = null;
    };
  }, []);

  const getStyles = (type: NotificationType) => {
    switch (type) {
      case 'success': return 'bg-green-50 border-green-200 text-green-800';
      case 'error': return 'bg-red-50 border-red-200 text-red-800';
      case 'warning': return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'info': return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`px-4 py-3 rounded-lg border shadow-lg ${getStyles(notification.type)}`}
        >
          <p className="text-sm">{notification.message}</p>
        </div>
      ))}
    </div>
  );
}
