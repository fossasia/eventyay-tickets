<template>
  <div class="exhibitor-detail">
    <!-- Loading State -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border" role="status">
        <span class="sr-only">{{ $t('common.loading') }}</span>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="alert alert-danger">
      <i class="fa fa-exclamation-triangle"></i>
      {{ error }}
    </div>

    <!-- Exhibitor Details -->
    <div v-else-if="exhibitor" class="exhibitor-content">
      <!-- Header -->
      <div class="exhibitor-header">
        <div class="row align-items-center">
          <div class="col-md-8">
            <div class="d-flex align-items-center">
              <button
                @click="goBack"
                class="btn btn-outline-secondary btn-sm me-3"
              >
                <i class="fa fa-arrow-left"></i>
                {{ $t('common.back') }}
              </button>
              <div>
                <h1 class="exhibitor-title">
                  {{ exhibitor.name }}
                  <span v-if="exhibitor.featured" class="badge badge-warning ms-2">
                    <i class="fa fa-star"></i>
                    {{ $t('exhibitors.featured') }}
                  </span>
                </h1>
                <div class="exhibitor-subtitle">
                  <i class="fa fa-map-marker-alt"></i>
                  {{ exhibitor.booth_name }}
                  <span class="booth-id">({{ exhibitor.booth_id }})</span>
                </div>
              </div>
            </div>
          </div>
          <div class="col-md-4 text-md-end">
            <div v-if="canManage" class="action-buttons">
              <button
                @click="editExhibitor"
                class="btn btn-primary"
              >
                <i class="fa fa-edit"></i>
                {{ $t('common.edit') }}
              </button>
              <div class="btn-group ms-2">
                <button
                  @click="copyKey"
                  class="btn btn-outline-secondary"
                  :title="$t('exhibitors.actions.copy_key')"
                >
                  <i class="fa fa-key"></i>
                </button>
                <button
                  @click="deleteExhibitor"
                  class="btn btn-outline-danger"
                  :title="$t('common.delete')"
                >
                  <i class="fa fa-trash"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="row">
        <!-- Left Column - Exhibitor Info -->
        <div class="col-lg-8">
          <!-- Basic Information -->
          <div class="info-card">
            <div class="row">
              <div class="col-md-4">
                <div class="exhibitor-logo-section">
                  <img
                    v-if="exhibitor.logo_url"
                    :src="exhibitor.logo_url"
                    :alt="exhibitor.name"
                    class="exhibitor-logo-large"
                  >
                  <div v-else class="exhibitor-logo-placeholder-large">
                    <i class="fa fa-building fa-4x"></i>
                  </div>
                </div>
              </div>
              <div class="col-md-8">
                <div class="exhibitor-info">
                  <h3>{{ $t('exhibitors.about') }}</h3>
                  <p v-if="exhibitor.description" class="exhibitor-description">
                    {{ exhibitor.description }}
                  </p>
                  <p v-else class="text-muted">
                    {{ $t('exhibitors.no_description') }}
                  </p>

                  <!-- Contact Information -->
                  <div class="contact-info">
                    <h4>{{ $t('exhibitors.contact_info') }}</h4>
                    <div class="contact-items">
                      <div v-if="exhibitor.email" class="contact-item">
                        <i class="fa fa-envelope"></i>
                        <a :href="`mailto:${exhibitor.email}`">{{ exhibitor.email }}</a>
                      </div>
                      <div v-if="exhibitor.url" class="contact-item">
                        <i class="fa fa-globe"></i>
                        <a :href="exhibitor.url" target="_blank" rel="noopener noreferrer">
                          {{ exhibitor.url }}
                          <i class="fa fa-external-link-alt ms-1"></i>
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Lead Management Section -->
          <div v-if="canManage" class="info-card">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <h3>{{ $t('exhibitors.lead_management') }}</h3>
              <button
                @click="exportLeads"
                class="btn btn-outline-primary btn-sm"
                :disabled="!leadStats.total_leads"
              >
                <i class="fa fa-download"></i>
                {{ $t('exhibitors.export_leads') }}
              </button>
            </div>

            <!-- Lead Statistics -->
            <div class="lead-stats-grid">
              <div class="stat-card">
                <div class="stat-number">{{ leadStats.total_leads || 0 }}</div>
                <div class="stat-label">{{ $t('exhibitors.total_leads') }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-number">{{ leadStats.leads_today || 0 }}</div>
                <div class="stat-label">{{ $t('exhibitors.leads_today') }}</div>
              </div>
              <div class="stat-card">
                <div class="stat-number">{{ leadStats.leads_this_week || 0 }}</div>
                <div class="stat-label">{{ $t('exhibitors.leads_this_week') }}</div>
              </div>
            </div>

            <!-- Follow-up Status Distribution -->
            <div class="follow-up-stats">
              <h4>{{ $t('exhibitors.follow_up_status') }}</h4>
              <div class="status-grid">
                <div class="status-item pending">
                  <span class="status-count">{{ leadStats.follow_up_pending || 0 }}</span>
                  <span class="status-label">{{ $t('leads.status.pending') }}</span>
                </div>
                <div class="status-item contacted">
                  <span class="status-count">{{ leadStats.follow_up_contacted || 0 }}</span>
                  <span class="status-label">{{ $t('leads.status.contacted') }}</span>
                </div>
                <div class="status-item qualified">
                  <span class="status-count">{{ leadStats.follow_up_qualified || 0 }}</span>
                  <span class="status-label">{{ $t('leads.status.qualified') }}</span>
                </div>
                <div class="status-item converted">
                  <span class="status-count">{{ leadStats.follow_up_converted || 0 }}</span>
                  <span class="status-label">{{ $t('leads.status.converted') }}</span>
                </div>
              </div>
            </div>

            <!-- Recent Leads -->
            <div v-if="recentLeads.length > 0" class="recent-leads">
              <h4>{{ $t('exhibitors.recent_leads') }}</h4>
              <div class="table-responsive">
                <table class="table table-sm">
                  <thead>
                    <tr>
                      <th>{{ $t('leads.attendee') }}</th>
                      <th>{{ $t('leads.scanned') }}</th>
                      <th>{{ $t('leads.status') }}</th>
                      <th>{{ $t('common.actions') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="lead in recentLeads" :key="lead.id">
                      <td>
                        <div>
                          <strong>{{ lead.attendee_name || 'Unknown' }}</strong>
                          <div v-if="lead.attendee_email" class="text-muted small">
                            {{ lead.attendee_email }}
                          </div>
                        </div>
                      </td>
                      <td>
                        <small>{{ formatDate(lead.scanned) }}</small>
                      </td>
                      <td>
                        <span 
                          class="badge"
                          :class="`badge-${getStatusColor(lead.follow_up_status)}`"
                        >
                          {{ $t(`leads.status.${lead.follow_up_status}`) }}
                        </span>
                      </td>
                      <td>
                        <button
                          @click="viewLead(lead)"
                          class="btn btn-outline-primary btn-xs"
                        >
                          <i class="fa fa-eye"></i>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="text-center mt-3">
                <button
                  @click="viewAllLeads"
                  class="btn btn-outline-primary"
                >
                  {{ $t('exhibitors.view_all_leads') }}
                </button>
              </div>
            </div>
          </div>

          <!-- Integration Information -->
          <div class="info-card">
            <h3>{{ $t('exhibitors.integrations') }}</h3>
            <div class="integration-grid">
              <!-- Tickets Integration -->
              <div class="integration-item">
                <div class="integration-icon">
                  <i class="fa fa-ticket-alt"></i>
                </div>
                <div class="integration-info">
                  <h5>{{ $t('exhibitors.tickets') }}</h5>
                  <p class="text-muted">{{ $t('exhibitors.tickets_description') }}</p>
                  <button class="btn btn-outline-primary btn-sm">
                    {{ $t('exhibitors.manage_tickets') }}
                  </button>
                </div>
              </div>

              <!-- Talks Integration -->
              <div class="integration-item">
                <div class="integration-icon">
                  <i class="fa fa-microphone"></i>
                </div>
                <div class="integration-info">
                  <h5>{{ $t('exhibitors.talks') }}</h5>
                  <p class="text-muted">{{ $t('exhibitors.talks_description') }}</p>
                  <button class="btn btn-outline-primary btn-sm">
                    {{ $t('exhibitors.manage_talks') }}
                  </button>
                </div>
              </div>

              <!-- Video Integration -->
              <div class="integration-item">
                <div class="integration-icon">
                  <i class="fa fa-video"></i>
                </div>
                <div class="integration-info">
                  <h5>{{ $t('exhibitors.videos') }}</h5>
                  <p class="text-muted">{{ $t('exhibitors.videos_description') }}</p>
                  <button class="btn btn-outline-primary btn-sm">
                    {{ $t('exhibitors.manage_videos') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column - Quick Actions & Settings -->
        <div class="col-lg-4">
          <!-- Quick Actions -->
          <div class="info-card">
            <h3>{{ $t('exhibitors.quick_actions') }}</h3>
            <div class="quick-actions">
              <button
                v-if="canManage"
                @click="regenerateKey"
                class="btn btn-outline-warning btn-block mb-2"
              >
                <i class="fa fa-refresh"></i>
                {{ $t('exhibitors.regenerate_key') }}
              </button>
              <button
                v-if="canManage"
                @click="toggleLeadScanning"
                class="btn btn-block mb-2"
                :class="exhibitor.lead_scanning_enabled ? 'btn-outline-danger' : 'btn-outline-success'"
              >
                <i class="fa" :class="exhibitor.lead_scanning_enabled ? 'fa-pause' : 'fa-play'"></i>
                {{ exhibitor.lead_scanning_enabled ? $t('exhibitors.disable_scanning') : $t('exhibitors.enable_scanning') }}
              </button>
              <button
                @click="downloadQR"
                class="btn btn-outline-info btn-block mb-2"
              >
                <i class="fa fa-qrcode"></i>
                {{ $t('exhibitors.download_qr') }}
              </button>
            </div>
          </div>

          <!-- Exhibitor Settings -->
          <div v-if="canManage" class="info-card">
            <h3>{{ $t('exhibitors.settings') }}</h3>
            <div class="settings-list">
              <div class="setting-item">
                <label class="form-check-label">
                  <input
                    v-model="exhibitor.lead_scanning_enabled"
                    type="checkbox"
                    class="form-check-input"
                    @change="updateSetting('lead_scanning_enabled', $event.target.checked)"
                  >
                  {{ $t('exhibitors.lead_scanning_enabled') }}
                </label>
              </div>
              <div class="setting-item">
                <label class="form-check-label">
                  <input
                    v-model="exhibitor.allow_voucher_access"
                    type="checkbox"
                    class="form-check-input"
                    @change="updateSetting('allow_voucher_access', $event.target.checked)"
                  >
                  {{ $t('exhibitors.allow_voucher_access') }}
                </label>
              </div>
              <div class="setting-item">
                <label class="form-check-label">
                  <input
                    v-model="exhibitor.allow_lead_access"
                    type="checkbox"
                    class="form-check-input"
                    @change="updateSetting('allow_lead_access', $event.target.checked)"
                  >
                  {{ $t('exhibitors.allow_lead_access') }}
                </label>
              </div>
              <div class="setting-item">
                <label class="form-check-label">
                  <input
                    v-model="exhibitor.featured"
                    type="checkbox"
                    class="form-check-input"
                    @change="updateSetting('featured', $event.target.checked)"
                  >
                  {{ $t('exhibitors.featured') }}
                </label>
              </div>
            </div>
          </div>

          <!-- QR Code -->
          <div class="info-card text-center">
            <h3>{{ $t('exhibitors.access_qr') }}</h3>
            <div class="qr-code-container">
              <canvas ref="qrCanvas" class="qr-code"></canvas>
            </div>
            <p class="text-muted small mt-2">
              {{ $t('exhibitors.qr_description') }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Modals -->
    <ExhibitorModal
      v-if="showEditModal"
      :exhibitor="exhibitor"
      :is-edit="true"
      @save="handleSaveExhibitor"
      @cancel="showEditModal = false"
    />

    <ConfirmModal
      v-if="showDeleteModal"
      :title="$t('exhibitors.delete.title')"
      :message="$t('exhibitors.delete.message', { name: exhibitor?.name })"
      @confirm="confirmDelete"
      @cancel="showDeleteModal = false"
    />
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useExhibitorStore } from '../stores/exhibitorStore'
import { useNotificationStore } from '../stores/notificationStore'
import ExhibitorModal from './ExhibitorModal.vue'
import ConfirmModal from './ConfirmModal.vue'

export default {
  name: 'ExhibitorDetail',
  components: {
    ExhibitorModal,
    ConfirmModal
  },
  props: {
    exhibitorId: {
      type: [String, Number],
      required: true
    },
    canManage: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const route = useRoute()
    const router = useRouter()
    const { t } = useI18n()
    const exhibitorStore = useExhibitorStore()
    const notificationStore = useNotificationStore()

    // Reactive data
    const showEditModal = ref(false)
    const showDeleteModal = ref(false)
    const qrCanvas = ref(null)

    // Computed properties
    const loading = computed(() => exhibitorStore.loading)
    const error = computed(() => exhibitorStore.error)
    const exhibitor = computed(() => exhibitorStore.currentExhibitor)
    const leadStats = computed(() => exhibitorStore.leadStats || {})
    const recentLeads = computed(() => exhibitorStore.recentLeads || [])

    // Methods
    const goBack = () => {
      router.push('/control/exhibitors/')
    }

    const editExhibitor = () => {
      showEditModal.value = true
    }

    const deleteExhibitor = () => {
      showDeleteModal.value = true
    }

    const copyKey = async () => {
      try {
        await navigator.clipboard.writeText(exhibitor.value.key)
        notificationStore.addSuccess(t('exhibitors.actions.key_copied'))
      } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = exhibitor.value.key
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
        notificationStore.addSuccess(t('exhibitors.actions.key_copied'))
      }
    }

    const regenerateKey = async () => {
      try {
        await exhibitorStore.regenerateExhibitorKey(props.exhibitorId)
        notificationStore.addSuccess(t('exhibitors.messages.key_regenerated'))
        generateQRCode() // Update QR code with new key
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.key_regenerate_error'))
      }
    }

    const toggleLeadScanning = async () => {
      try {
        const newValue = !exhibitor.value.lead_scanning_enabled
        await updateSetting('lead_scanning_enabled', newValue)
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.update_error'))
      }
    }

    const updateSetting = async (field, value) => {
      try {
        await exhibitorStore.updateExhibitor(props.exhibitorId, { [field]: value })
        notificationStore.addSuccess(t('exhibitors.messages.updated'))
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.update_error'))
      }
    }

    const handleSaveExhibitor = async (exhibitorData) => {
      try {
        await exhibitorStore.updateExhibitor(props.exhibitorId, exhibitorData)
        notificationStore.addSuccess(t('exhibitors.messages.updated'))
        showEditModal.value = false
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.save_error'))
      }
    }

    const confirmDelete = async () => {
      try {
        await exhibitorStore.deleteExhibitor(props.exhibitorId)
        notificationStore.addSuccess(t('exhibitors.messages.deleted'))
        router.push('/control/exhibitors/')
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.delete_error'))
      }
    }

    const exportLeads = async () => {
      try {
        await exhibitorStore.exportLeads(props.exhibitorId)
        notificationStore.addSuccess(t('exhibitors.messages.export_started'))
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.export_error'))
      }
    }

    const viewLead = (lead) => {
      // Navigate to lead detail or open modal
      console.log('View lead:', lead)
    }

    const viewAllLeads = () => {
      router.push(`/control/exhibitors/${props.exhibitorId}/leads/`)
    }

    const downloadQR = () => {
      if (qrCanvas.value) {
        const link = document.createElement('a')
        link.download = `exhibitor-${exhibitor.value.booth_id}-qr.png`
        link.href = qrCanvas.value.toDataURL()
        link.click()
      }
    }

    const generateQRCode = async () => {
      if (!exhibitor.value || !qrCanvas.value) return

      try {
        // Use QRCode library to generate QR code
        const QRCode = window.QRCode
        if (QRCode) {
          await QRCode.toCanvas(qrCanvas.value, exhibitor.value.key, {
            width: 200,
            margin: 2,
            color: {
              dark: '#000000',
              light: '#FFFFFF'
            }
          })
        }
      } catch (error) {
        console.error('Error generating QR code:', error)
      }
    }

    const formatDate = (dateString) => {
      return new Date(dateString).toLocaleString()
    }

    const getStatusColor = (status) => {
      const colors = {
        pending: 'warning',
        contacted: 'info',
        qualified: 'primary',
        converted: 'success'
      }
      return colors[status] || 'secondary'
    }

    // Lifecycle
    onMounted(async () => {
      await exhibitorStore.fetchExhibitor(props.exhibitorId)
      await exhibitorStore.fetchLeadStats(props.exhibitorId)
      await exhibitorStore.fetchRecentLeads(props.exhibitorId)
      
      nextTick(() => {
        generateQRCode()
      })
    })

    return {
      // Reactive data
      showEditModal,
      showDeleteModal,
      qrCanvas,
      
      // Computed
      loading,
      error,
      exhibitor,
      leadStats,
      recentLeads,
      
      // Methods
      goBack,
      editExhibitor,
      deleteExhibitor,
      copyKey,
      regenerateKey,
      toggleLeadScanning,
      updateSetting,
      handleSaveExhibitor,
      confirmDelete,
      exportLeads,
      viewLead,
      viewAllLeads,
      downloadQR,
      formatDate,
      getStatusColor
    }
  }
}
</script>

<style scoped>
.exhibitor-detail {
  padding: 20px;
}

.exhibitor-header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #dee2e6;
}

.exhibitor-title {
  font-size: 2rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.exhibitor-subtitle {
  color: #6c757d;
  font-size: 1.1rem;
  display: flex;
  align-items: center;
  gap: 8px;
}

.booth-id {
  font-family: monospace;
  background: #f8f9fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9rem;
}

.info-card {
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.exhibitor-logo-section {
  text-align: center;
}

.exhibitor-logo-large {
  max-width: 100%;
  max-height: 200px;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.exhibitor-logo-placeholder-large {
  width: 200px;
  height: 200px;
  background: #f8f9fa;
  border: 2px dashed #dee2e6;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c757d;
  margin: 0 auto;
}

.exhibitor-description {
  font-size: 1.1rem;
  line-height: 1.6;
  color: #555;
  margin-bottom: 24px;
}

.contact-info h4 {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 16px;
  color: #333;
}

.contact-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.contact-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1rem;
}

.contact-item i {
  width: 20px;
  color: #007bff;
}

.contact-item a {
  color: #007bff;
  text-decoration: none;
}

.contact-item a:hover {
  text-decoration: underline;
}

.lead-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid #e9ecef;
}

.stat-number {
  font-size: 2rem;
  font-weight: bold;
  color: #007bff;
  margin-bottom: 4px;
}

.stat-label {
  color: #6c757d;
  font-size: 0.9rem;
}

.follow-up-stats h4 {
  margin-bottom: 16px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.status-item {
  text-align: center;
  padding: 12px;
  border-radius: 8px;
  border: 2px solid;
}

.status-item.pending {
  border-color: #ffc107;
  background: #fff9e6;
}

.status-item.contacted {
  border-color: #17a2b8;
  background: #e6f7ff;
}

.status-item.qualified {
  border-color: #007bff;
  background: #e6f3ff;
}

.status-item.converted {
  border-color: #28a745;
  background: #e6f7e6;
}

.status-count {
  display: block;
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 4px;
}

.status-label {
  font-size: 0.85rem;
  color: #666;
}

.integration-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.integration-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 16px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  background: #f8f9fa;
}

.integration-icon {
  width: 48px;
  height: 48px;
  background: #007bff;
  color: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}

.integration-info h5 {
  margin-bottom: 8px;
  font-size: 1rem;
  font-weight: 600;
}

.integration-info p {
  margin-bottom: 12px;
  font-size: 0.9rem;
}

.quick-actions .btn-block {
  width: 100%;
  margin-bottom: 8px;
}

.settings-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-check-input {
  margin: 0;
}

.qr-code-container {
  display: flex;
  justify-content: center;
  margin: 16px 0;
}

.qr-code {
  border: 1px solid #dee2e6;
  border-radius: 8px;
}

.recent-leads h4 {
  margin-bottom: 16px;
}

.btn-xs {
  padding: 2px 6px;
  font-size: 0.75rem;
}

@media (max-width: 768px) {
  .exhibitor-header .d-flex {
    flex-direction: column;
    align-items: flex-start !important;
  }
  
  .action-buttons {
    margin-top: 16px;
  }
  
  .lead-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .status-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .integration-grid {
    grid-template-columns: 1fr;
  }
  
  .integration-item {
    flex-direction: column;
    text-align: center;
  }
}
</style>