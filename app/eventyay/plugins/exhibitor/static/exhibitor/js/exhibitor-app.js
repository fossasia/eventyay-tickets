// Exhibitor Vue.js 3 Application
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'

// Import components
import ExhibitorDirectory from '../components/ExhibitorDirectory.vue'
import ExhibitorDetail from '../components/ExhibitorDetail.vue'
import ExhibitorCard from '../components/ExhibitorCard.vue'
import ExhibitorModal from '../components/ExhibitorModal.vue'
import ConfirmModal from '../components/ConfirmModal.vue'

// Import stores
import { useExhibitorStore } from '../stores/exhibitorStore.js'
import { useNotificationStore } from '../stores/notificationStore.js'

// Import translations
import en from '../locales/en.json'
import de from '../locales/de.json'

// Create i18n instance
const i18n = createI18n({
  locale: document.documentElement.lang || 'en',
  fallbackLocale: 'en',
  messages: {
    en,
    de
  }
})

// Create Pinia instance
const pinia = createPinia()

// Global component registration function
const registerGlobalComponents = (app) => {
  app.component('ExhibitorDirectory', ExhibitorDirectory)
  app.component('ExhibitorDetail', ExhibitorDetail)
  app.component('ExhibitorCard', ExhibitorCard)
  app.component('ExhibitorModal', ExhibitorModal)
  app.component('ConfirmModal', ConfirmModal)
}

// Initialize Vue app for exhibitor directory
const initExhibitorDirectory = (elementId = '#exhibitor-directory-app') => {
  const element = document.querySelector(elementId)
  if (!element) return null

  const app = createApp({
    template: `
      <ExhibitorDirectory 
        :can-manage-exhibitors="canManageExhibitors"
      />
    `,
    data() {
      return {
        canManageExhibitors: element.dataset.canManage === 'true'
      }
    }
  })

  app.use(pinia)
  app.use(i18n)
  registerGlobalComponents(app)

  return app.mount(element)
}

// Initialize Vue app for exhibitor detail
const initExhibitorDetail = (elementId = '#exhibitor-detail-app') => {
  const element = document.querySelector(elementId)
  if (!element) return null

  const app = createApp({
    template: `
      <ExhibitorDetail 
        :exhibitor-id="exhibitorId"
        :can-manage="canManage"
      />
    `,
    data() {
      return {
        exhibitorId: parseInt(element.dataset.exhibitorId),
        canManage: element.dataset.canManage === 'true'
      }
    }
  })

  app.use(pinia)
  app.use(i18n)
  registerGlobalComponents(app)

  return app.mount(element)
}

// Initialize notification system
const initNotifications = (elementId = '#notifications-container') => {
  const element = document.querySelector(elementId)
  if (!element) {
    // Create notifications container if it doesn't exist
    const container = document.createElement('div')
    container.id = 'notifications-container'
    container.className = 'notifications-container'
    document.body.appendChild(container)
  }

  const app = createApp({
    template: `
      <div class="notifications-wrapper">
        <transition-group name="notification" tag="div" class="notifications-list">
          <div
            v-for="notification in notifications"
            :key="notification.id"
            class="notification"
            :class="'notification-' + notification.type"
            @click="removeNotification(notification.id)"
          >
            <div class="notification-content">
              <i class="notification-icon" :class="getIconClass(notification.type)"></i>
              <span class="notification-message">{{ notification.message }}</span>
              <button class="notification-close" @click.stop="removeNotification(notification.id)">
                <i class="fa fa-times"></i>
              </button>
            </div>
          </div>
        </transition-group>
      </div>
    `,
    setup() {
      const notificationStore = useNotificationStore()
      
      const getIconClass = (type) => {
        const icons = {
          success: 'fa fa-check-circle',
          error: 'fa fa-exclamation-circle',
          warning: 'fa fa-exclamation-triangle',
          info: 'fa fa-info-circle'
        }
        return icons[type] || icons.info
      }
      
      return {
        notifications: notificationStore.notifications,
        removeNotification: notificationStore.removeNotification,
        getIconClass
      }
    }
  })

  app.use(pinia)
  app.use(i18n)

  return app.mount(element || document.querySelector('#notifications-container'))
}

// Auto-initialize based on page content
document.addEventListener('DOMContentLoaded', () => {
  // Initialize notifications first
  initNotifications()
  
  // Initialize appropriate app based on page content
  if (document.querySelector('#exhibitor-directory-app')) {
    initExhibitorDirectory()
  }
  
  if (document.querySelector('#exhibitor-detail-app')) {
    initExhibitorDetail()
  }
})

// Export for manual initialization
window.ExhibitorApp = {
  initExhibitorDirectory,
  initExhibitorDetail,
  initNotifications,
  createApp,
  pinia,
  i18n
}

// CSS for notifications
const notificationStyles = `
.notifications-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  pointer-events: none;
}

.notifications-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 400px;
}

.notification {
  pointer-events: auto;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border-left: 4px solid;
  cursor: pointer;
  transition: all 0.3s ease;
}

.notification:hover {
  transform: translateX(-5px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
}

.notification-success {
  border-left-color: #28a745;
}

.notification-error {
  border-left-color: #dc3545;
}

.notification-warning {
  border-left-color: #ffc107;
}

.notification-info {
  border-left-color: #17a2b8;
}

.notification-content {
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 12px;
}

.notification-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

.notification-success .notification-icon {
  color: #28a745;
}

.notification-error .notification-icon {
  color: #dc3545;
}

.notification-warning .notification-icon {
  color: #ffc107;
}

.notification-info .notification-icon {
  color: #17a2b8;
}

.notification-message {
  flex: 1;
  font-size: 0.9rem;
  line-height: 1.4;
}

.notification-close {
  background: none;
  border: none;
  color: #6c757d;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.notification-close:hover {
  background-color: #f8f9fa;
  color: #495057;
}

/* Transition animations */
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.notification-move {
  transition: transform 0.3s ease;
}

@media (max-width: 768px) {
  .notifications-container {
    top: 10px;
    right: 10px;
    left: 10px;
  }
  
  .notifications-list {
    max-width: none;
  }
  
  .notification-content {
    padding: 12px;
  }
}
`

// Inject notification styles
const styleSheet = document.createElement('style')
styleSheet.textContent = notificationStyles
document.head.appendChild(styleSheet)