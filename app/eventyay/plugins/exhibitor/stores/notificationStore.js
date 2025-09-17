import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNotificationStore = defineStore('notification', () => {
  // State
  const notifications = ref([])
  let nextId = 1

  // Actions
  const addNotification = (message, type = 'info', duration = 5000) => {
    const notification = {
      id: nextId++,
      message,
      type,
      timestamp: Date.now(),
      duration
    }
    
    notifications.value.push(notification)
    
    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        removeNotification(notification.id)
      }, duration)
    }
    
    return notification.id
  }

  const addSuccess = (message, duration = 4000) => {
    return addNotification(message, 'success', duration)
  }

  const addError = (message, duration = 6000) => {
    return addNotification(message, 'error', duration)
  }

  const addWarning = (message, duration = 5000) => {
    return addNotification(message, 'warning', duration)
  }

  const addInfo = (message, duration = 4000) => {
    return addNotification(message, 'info', duration)
  }

  const removeNotification = (id) => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  const clearAll = () => {
    notifications.value = []
  }

  const clearByType = (type) => {
    notifications.value = notifications.value.filter(n => n.type !== type)
  }

  return {
    // State
    notifications,
    
    // Actions
    addNotification,
    addSuccess,
    addError,
    addWarning,
    addInfo,
    removeNotification,
    clearAll,
    clearByType
  }
})