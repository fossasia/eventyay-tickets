<template>
  <div class="modal fade show" style="display: block;" @click.self="$emit('cancel')">
    <div class="modal-dialog modal-lg">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">
            {{ isEdit ? $t('exhibitors.edit_title') : $t('exhibitors.create_title') }}
          </h5>
          <button type="button" class="btn-close" @click="$emit('cancel')"></button>
        </div>
        
        <form @submit.prevent="handleSubmit">
          <div class="modal-body">
            <!-- Name -->
            <div class="mb-3">
              <label class="form-label required">{{ $t('exhibitors.fields.name') }}</label>
              <input
                v-model="form.name"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': errors.name }"
                required
              >
              <div v-if="errors.name" class="invalid-feedback">
                {{ errors.name }}
              </div>
            </div>

            <!-- Description -->
            <div class="mb-3">
              <label class="form-label">{{ $t('exhibitors.fields.description') }}</label>
              <textarea
                v-model="form.description"
                class="form-control"
                rows="3"
                :class="{ 'is-invalid': errors.description }"
              ></textarea>
              <div v-if="errors.description" class="invalid-feedback">
                {{ errors.description }}
              </div>
            </div>

            <!-- Logo Upload -->
            <div class="mb-3">
              <label class="form-label">{{ $t('exhibitors.fields.logo') }}</label>
              <div class="logo-upload-area">
                <div v-if="logoPreview" class="logo-preview">
                  <img :src="logoPreview" :alt="form.name" class="preview-image">
                  <button
                    type="button"
                    class="btn btn-sm btn-outline-danger remove-logo"
                    @click="removeLogo"
                  >
                    <i class="fa fa-times"></i>
                  </button>
                </div>
                <div v-else class="upload-placeholder" @click="$refs.logoInput.click()">
                  <i class="fa fa-cloud-upload-alt fa-2x mb-2"></i>
                  <p>{{ $t('exhibitors.upload_logo') }}</p>
                  <small class="text-muted">{{ $t('exhibitors.logo_requirements') }}</small>
                </div>
                <input
                  ref="logoInput"
                  type="file"
                  accept="image/*"
                  class="d-none"
                  @change="handleLogoUpload"
                >
              </div>
              <div v-if="errors.logo" class="text-danger small mt-1">
                {{ errors.logo }}
              </div>
            </div>

            <div class="row">
              <!-- Email -->
              <div class="col-md-6 mb-3">
                <label class="form-label">{{ $t('exhibitors.fields.email') }}</label>
                <input
                  v-model="form.email"
                  type="email"
                  class="form-control"
                  :class="{ 'is-invalid': errors.email }"
                >
                <div v-if="errors.email" class="invalid-feedback">
                  {{ errors.email }}
                </div>
              </div>

              <!-- Website URL -->
              <div class="col-md-6 mb-3">
                <label class="form-label">{{ $t('exhibitors.fields.url') }}</label>
                <input
                  v-model="form.url"
                  type="url"
                  class="form-control"
                  :class="{ 'is-invalid': errors.url }"
                >
                <div v-if="errors.url" class="invalid-feedback">
                  {{ errors.url }}
                </div>
              </div>
            </div>

            <div class="row">
              <!-- Booth Name -->
              <div class="col-md-6 mb-3">
                <label class="form-label required">{{ $t('exhibitors.fields.booth_name') }}</label>
                <input
                  v-model="form.booth_name"
                  type="text"
                  class="form-control"
                  :class="{ 'is-invalid': errors.booth_name }"
                  required
                >
                <div v-if="errors.booth_name" class="invalid-feedback">
                  {{ errors.booth_name }}
                </div>
              </div>

              <!-- Booth ID -->
              <div class="col-md-6 mb-3">
                <label class="form-label">{{ $t('exhibitors.fields.booth_id') }}</label>
                <input
                  v-model="form.booth_id"
                  type="text"
                  class="form-control"
                  :class="{ 'is-invalid': errors.booth_id }"
                  :placeholder="$t('exhibitors.booth_id_placeholder')"
                >
                <div v-if="errors.booth_id" class="invalid-feedback">
                  {{ errors.booth_id }}
                </div>
                <small class="form-text text-muted">
                  {{ $t('exhibitors.booth_id_help') }}
                </small>
              </div>
            </div>

            <!-- Settings -->
            <div class="mb-3">
              <label class="form-label">{{ $t('exhibitors.settings') }}</label>
              <div class="settings-checkboxes">
                <div class="form-check">
                  <input
                    v-model="form.lead_scanning_enabled"
                    type="checkbox"
                    class="form-check-input"
                    id="lead_scanning_enabled"
                  >
                  <label class="form-check-label" for="lead_scanning_enabled">
                    {{ $t('exhibitors.lead_scanning_enabled') }}
                  </label>
                </div>
                <div class="form-check">
                  <input
                    v-model="form.allow_voucher_access"
                    type="checkbox"
                    class="form-check-input"
                    id="allow_voucher_access"
                  >
                  <label class="form-check-label" for="allow_voucher_access">
                    {{ $t('exhibitors.allow_voucher_access') }}
                  </label>
                </div>
                <div class="form-check">
                  <input
                    v-model="form.allow_lead_access"
                    type="checkbox"
                    class="form-check-input"
                    id="allow_lead_access"
                  >
                  <label class="form-check-label" for="allow_lead_access">
                    {{ $t('exhibitors.allow_lead_access') }}
                  </label>
                </div>
                <div class="form-check">
                  <input
                    v-model="form.featured"
                    type="checkbox"
                    class="form-check-input"
                    id="featured"
                  >
                  <label class="form-check-label" for="featured">
                    {{ $t('exhibitors.featured') }}
                  </label>
                </div>
              </div>
            </div>

            <!-- Sort Order -->
            <div class="mb-3">
              <label class="form-label">{{ $t('exhibitors.fields.sort_order') }}</label>
              <input
                v-model.number="form.sort_order"
                type="number"
                class="form-control"
                :class="{ 'is-invalid': errors.sort_order }"
                min="0"
              >
              <div v-if="errors.sort_order" class="invalid-feedback">
                {{ errors.sort_order }}
              </div>
              <small class="form-text text-muted">
                {{ $t('exhibitors.sort_order_help') }}
              </small>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="$emit('cancel')">
              {{ $t('common.cancel') }}
            </button>
            <button type="submit" class="btn btn-primary" :disabled="submitting">
              <span v-if="submitting" class="spinner-border spinner-border-sm me-2"></span>
              {{ isEdit ? $t('common.save_changes') : $t('common.create') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
  <div class="modal-backdrop fade show"></div>
</template>

<script>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

export default {
  name: 'ExhibitorModal',
  props: {
    exhibitor: {
      type: Object,
      default: null
    },
    isEdit: {
      type: Boolean,
      default: false
    }
  },
  emits: ['save', 'cancel'],
  setup(props, { emit }) {
    const { t } = useI18n()
    
    // Reactive data
    const submitting = ref(false)
    const logoPreview = ref(null)
    const logoInput = ref(null)
    
    const form = reactive({
      name: '',
      description: '',
      email: '',
      url: '',
      booth_name: '',
      booth_id: '',
      logo: null,
      lead_scanning_enabled: false,
      allow_voucher_access: false,
      allow_lead_access: false,
      featured: false,
      sort_order: 0
    })
    
    const errors = reactive({})
    
    // Initialize form data
    const initializeForm = () => {
      if (props.isEdit && props.exhibitor) {
        Object.keys(form).forEach(key => {
          if (props.exhibitor[key] !== undefined) {
            form[key] = props.exhibitor[key]
          }
        })
        
        // Set logo preview if exists
        if (props.exhibitor.logo_url) {
          logoPreview.value = props.exhibitor.logo_url
        }
      } else {
        // Reset form for create mode
        Object.keys(form).forEach(key => {
          if (typeof form[key] === 'boolean') {
            form[key] = false
          } else if (typeof form[key] === 'number') {
            form[key] = 0
          } else {
            form[key] = ''
          }
        })
        logoPreview.value = null
      }
    }
    
    // Validation
    const validateForm = () => {
      // Clear previous errors
      Object.keys(errors).forEach(key => {
        delete errors[key]
      })
      
      let isValid = true
      
      // Required fields
      if (!form.name || form.name.trim().length < 2) {
        errors.name = t('exhibitors.validation.name_required')
        isValid = false
      }
      
      if (!form.booth_name || form.booth_name.trim().length === 0) {
        errors.booth_name = t('exhibitors.validation.booth_name_required')
        isValid = false
      }
      
      // Email validation
      if (form.email && !isValidEmail(form.email)) {
        errors.email = t('exhibitors.validation.email_invalid')
        isValid = false
      }
      
      // URL validation
      if (form.url && !isValidUrl(form.url)) {
        errors.url = t('exhibitors.validation.url_invalid')
        isValid = false
      }
      
      // Logo validation
      if (form.logo && form.logo instanceof File) {
        if (form.logo.size > 5 * 1024 * 1024) { // 5MB
          errors.logo = t('exhibitors.validation.logo_too_large')
          isValid = false
        }
        
        if (!form.logo.type.startsWith('image/')) {
          errors.logo = t('exhibitors.validation.logo_invalid_type')
          isValid = false
        }
      }
      
      return isValid
    }
    
    const isValidEmail = (email) => {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      return emailRegex.test(email)
    }
    
    const isValidUrl = (url) => {
      try {
        new URL(url)
        return true
      } catch {
        return false
      }
    }
    
    // Handle logo upload
    const handleLogoUpload = (event) => {
      const file = event.target.files[0]
      if (file) {
        form.logo = file
        
        // Create preview
        const reader = new FileReader()
        reader.onload = (e) => {
          logoPreview.value = e.target.result
        }
        reader.readAsDataURL(file)
      }
    }
    
    const removeLogo = () => {
      form.logo = null
      logoPreview.value = null
      if (logoInput.value) {
        logoInput.value.value = ''
      }
    }
    
    // Handle form submission
    const handleSubmit = async () => {
      if (!validateForm()) {
        return
      }
      
      submitting.value = true
      
      try {
        // Prepare form data
        const formData = { ...form }
        
        // Clean up empty strings
        Object.keys(formData).forEach(key => {
          if (formData[key] === '') {
            formData[key] = null
          }
        })
        
        emit('save', formData)
      } catch (error) {
        console.error('Error submitting form:', error)
      } finally {
        submitting.value = false
      }
    }
    
    // Watch for prop changes
    watch(() => props.exhibitor, initializeForm, { immediate: true })
    
    // Lifecycle
    onMounted(() => {
      initializeForm()
    })
    
    return {
      form,
      errors,
      submitting,
      logoPreview,
      logoInput,
      handleLogoUpload,
      removeLogo,
      handleSubmit,
      validateForm
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

.required::after {
  content: ' *';
  color: #dc3545;
}

.logo-upload-area {
  border: 2px dashed #dee2e6;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  transition: border-color 0.2s;
  position: relative;
}

.logo-upload-area:hover {
  border-color: #007bff;
}

.upload-placeholder {
  cursor: pointer;
  color: #6c757d;
}

.upload-placeholder:hover {
  color: #007bff;
}

.logo-preview {
  position: relative;
  display: inline-block;
}

.preview-image {
  max-width: 200px;
  max-height: 150px;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.remove-logo {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
}

.settings-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.form-check {
  margin-bottom: 0;
}

.form-check-label {
  font-weight: 500;
  cursor: pointer;
}

.spinner-border-sm {
  width: 1rem;
  height: 1rem;
}

@media (max-width: 768px) {
  .modal-dialog {
    margin: 10px;
    max-width: calc(100% - 20px);
  }
  
  .settings-checkboxes {
    padding: 12px;
  }
}
</style>