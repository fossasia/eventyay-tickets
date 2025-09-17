<template>
  <div class="exhibitor-card" :class="{ featured: exhibitor.featured }">
    <!-- Featured Badge -->
    <div v-if="exhibitor.featured" class="featured-badge">
      <i class="fa fa-star"></i>
      {{ $t('exhibitors.featured') }}
    </div>

    <!-- Exhibitor Logo -->
    <div class="exhibitor-logo-container">
      <img
        v-if="exhibitor.logo_url"
        :src="exhibitor.logo_url"
        :alt="exhibitor.name"
        class="exhibitor-logo"
        @error="handleImageError"
      >
      <div v-else class="exhibitor-logo-placeholder">
        <i class="fa fa-building fa-2x"></i>
      </div>
    </div>

    <!-- Exhibitor Info -->
    <div class="exhibitor-info">
      <h3 class="exhibitor-name" :title="exhibitor.name">
        {{ exhibitor.name }}
      </h3>
      
      <div class="exhibitor-booth">
        <i class="fa fa-map-marker-alt"></i>
        {{ exhibitor.booth_name }}
      </div>

      <p v-if="exhibitor.description" class="exhibitor-description">
        {{ truncateText(exhibitor.description, 120) }}
      </p>

      <!-- Stats -->
      <div class="exhibitor-stats">
        <div class="stat-item">
          <i class="fa fa-users"></i>
          <span>{{ exhibitor.lead_count || 0 }} {{ $t('exhibitors.leads') }}</span>
        </div>
        <div v-if="exhibitor.recent_leads_count" class="stat-item recent">
          <i class="fa fa-clock"></i>
          <span>{{ exhibitor.recent_leads_count }} {{ $t('exhibitors.recent') }}</span>
        </div>
      </div>

      <!-- Contact Info -->
      <div class="exhibitor-contact">
        <a
          v-if="exhibitor.url"
          :href="exhibitor.url"
          target="_blank"
          rel="noopener noreferrer"
          class="contact-link"
          @click.stop
        >
          <i class="fa fa-external-link-alt"></i>
          {{ $t('exhibitors.visit_website') }}
        </a>
        <a
          v-if="exhibitor.email"
          :href="`mailto:${exhibitor.email}`"
          class="contact-link"
          @click.stop
        >
          <i class="fa fa-envelope"></i>
          {{ $t('exhibitors.contact') }}
        </a>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="exhibitor-actions">
      <button
        @click="$emit('view', exhibitor)"
        class="btn btn-primary btn-sm"
      >
        <i class="fa fa-eye"></i>
        {{ $t('common.view') }}
      </button>
      
      <div v-if="canManage" class="admin-actions">
        <div class="btn-group btn-group-sm">
          <button
            @click.stop="$emit('edit', exhibitor)"
            class="btn btn-outline-secondary"
            :title="$t('common.edit')"
          >
            <i class="fa fa-edit"></i>
          </button>
          <button
            @click.stop="$emit('copy-key', exhibitor)"
            class="btn btn-outline-secondary"
            :title="$t('exhibitors.actions.copy_key')"
          >
            <i class="fa fa-key"></i>
          </button>
          <button
            @click.stop="$emit('delete', exhibitor)"
            class="btn btn-outline-danger"
            :title="$t('common.delete')"
          >
            <i class="fa fa-trash"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Status Indicator -->
    <div class="status-indicator" :class="{ active: exhibitor.is_active }">
      <span class="status-dot"></span>
      {{ exhibitor.is_active ? $t('common.active') : $t('common.inactive') }}
    </div>
  </div>
</template>

<script>
import { useI18n } from 'vue-i18n'

export default {
  name: 'ExhibitorCard',
  props: {
    exhibitor: {
      type: Object,
      required: true
    },
    canManage: {
      type: Boolean,
      default: false
    }
  },
  emits: ['view', 'edit', 'delete', 'copy-key'],
  setup() {
    const { t } = useI18n()

    const truncateText = (text, maxLength) => {
      if (!text) return ''
      return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
    }

    const handleImageError = (event) => {
      // Hide broken image and show placeholder
      event.target.style.display = 'none'
      const placeholder = event.target.parentNode.querySelector('.exhibitor-logo-placeholder')
      if (placeholder) {
        placeholder.style.display = 'flex'
      }
    }

    return {
      t,
      truncateText,
      handleImageError
    }
  }
}
</script>

<style scoped>
.exhibitor-card {
  background: white;
  border: 1px solid #dee2e6;
  border-radius: 12px;
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
  cursor: pointer;
}

.exhibitor-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  border-color: #007bff;
}

.exhibitor-card.featured {
  border-color: #ffc107;
  background: linear-gradient(135deg, #fff9e6 0%, #ffffff 100%);
}

.featured-badge {
  position: absolute;
  top: -1px;
  right: -1px;
  background: linear-gradient(135deg, #ffc107, #ff8c00);
  color: white;
  padding: 4px 12px;
  border-radius: 0 12px 0 12px;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.exhibitor-logo-container {
  text-align: center;
  margin-bottom: 16px;
  position: relative;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.exhibitor-logo {
  max-width: 100%;
  max-height: 80px;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.exhibitor-logo-placeholder {
  width: 80px;
  height: 80px;
  background: #f8f9fa;
  border: 2px dashed #dee2e6;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.exhibitor-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.exhibitor-name {
  font-size: 1.25rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.exhibitor-booth {
  color: #6c757d;
  font-size: 0.9rem;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.exhibitor-booth i {
  color: #007bff;
}

.exhibitor-description {
  color: #666;
  font-size: 0.9rem;
  line-height: 1.4;
  margin-bottom: 16px;
  flex: 1;
}

.exhibitor-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: #6c757d;
}

.stat-item i {
  color: #007bff;
  width: 14px;
}

.stat-item.recent {
  color: #28a745;
}

.stat-item.recent i {
  color: #28a745;
}

.exhibitor-contact {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.contact-link {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #007bff;
  text-decoration: none;
  font-size: 0.85rem;
  transition: color 0.2s;
}

.contact-link:hover {
  color: #0056b3;
  text-decoration: none;
}

.contact-link i {
  width: 14px;
}

.exhibitor-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid #f1f3f4;
}

.admin-actions {
  margin-left: 12px;
}

.btn-group-sm .btn {
  padding: 4px 8px;
  font-size: 0.75rem;
}

.status-indicator {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: #6c757d;
  background: rgba(255, 255, 255, 0.9);
  padding: 4px 8px;
  border-radius: 12px;
  backdrop-filter: blur(4px);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #dc3545;
}

.status-indicator.active .status-dot {
  background: #28a745;
}

.status-indicator.active {
  color: #28a745;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .exhibitor-card {
    padding: 16px;
  }
  
  .exhibitor-name {
    font-size: 1.1rem;
  }
  
  .exhibitor-stats {
    flex-direction: column;
    gap: 8px;
  }
  
  .exhibitor-actions {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  
  .admin-actions {
    margin-left: 0;
  }
  
  .admin-actions .btn-group {
    width: 100%;
    display: flex;
  }
  
  .admin-actions .btn {
    flex: 1;
  }
}

/* Animation for featured cards */
.exhibitor-card.featured::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 12px;
  padding: 2px;
  background: linear-gradient(45deg, #ffc107, #ff8c00, #ffc107);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.exhibitor-card.featured:hover::before {
  opacity: 1;
}
</style>