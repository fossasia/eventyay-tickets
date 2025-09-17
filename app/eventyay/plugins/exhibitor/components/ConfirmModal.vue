<template>
  <div class="modal fade show" style="display: block;" @click.self="$emit('cancel')">
    <div class="modal-dialog">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{{ title }}</h5>
          <button type="button" class="btn-close" @click="$emit('cancel')"></button>
        </div>
        
        <div class="modal-body">
          <div class="d-flex align-items-center">
            <div class="me-3">
              <i class="fa fa-exclamation-triangle fa-2x text-warning"></i>
            </div>
            <div>
              <p class="mb-0">{{ message }}</p>
              <small v-if="subMessage" class="text-muted">{{ subMessage }}</small>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="$emit('cancel')">
            {{ cancelText || $t('common.cancel') }}
          </button>
          <button 
            type="button" 
            class="btn"
            :class="confirmButtonClass"
            @click="$emit('confirm')"
            :disabled="confirming"
          >
            <span v-if="confirming" class="spinner-border spinner-border-sm me-2"></span>
            {{ confirmText || $t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show"></div>
</template>

<script>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export default {
  name: 'ConfirmModal',
  props: {
    title: {
      type: String,
      required: true
    },
    message: {
      type: String,
      required: true
    },
    subMessage: {
      type: String,
      default: null
    },
    confirmText: {
      type: String,
      default: null
    },
    cancelText: {
      type: String,
      default: null
    },
    variant: {
      type: String,
      default: 'danger',
      validator: (value) => ['danger', 'warning', 'primary', 'success'].includes(value)
    },
    confirming: {
      type: Boolean,
      default: false
    }
  },
  emits: ['confirm', 'cancel'],
  setup(props) {
    const { t } = useI18n()
    
    const confirmButtonClass = computed(() => {
      const baseClass = 'btn-'
      return baseClass + props.variant
    })
    
    return {
      confirmButtonClass,
      t
    }
  }
}
</script>

<style scoped>
.modal {
  z-index: 1050;
}

.modal-backdrop {
  z-index: 1040;
}

.spinner-border-sm {
  width: 1rem;
  height: 1rem;
}
</style>