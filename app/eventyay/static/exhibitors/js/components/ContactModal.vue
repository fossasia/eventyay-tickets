<template>
  <div 
    v-if="show" 
    class="modal-overlay" 
    @click="closeModal"
  >
    <div 
      class="modal-dialog" 
      @click.stop
      role="dialog"
      aria-labelledby="contactModalTitle"
      aria-describedby="contactModalDescription"
    >
      <div class="modal-content">
        <!-- Modal Header -->
        <div class="modal-header">
          <h4 id="contactModalTitle" class="modal-title">
            <i class="fas fa-envelope me-2"></i>
            {{ $t('Contact {name}', { name: exhibitor?.name || 'Exhibitor' }) }}
          </h4>
          <button 
            type="button" 
            class="btn-close" 
            @click="closeModal"
            :aria-label="$t('Close')"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>

        <!-- Modal Body -->
        <div class="modal-body">
          <p id="contactModalDescription" class="modal-description">
            {{ $t('Send a message to {name} and they will get back to you soon.', { name: exhibitor?.name }) }}
          </p>

          <!-- Success Message -->
          <div v-if="submitted" class="alert alert-success" role="alert">
            <i class="fas fa-check-circle me-2"></i>
            {{ $t('Your message has been sent successfully! The exhibitor will get back to you soon.') }}
          </div>

          <!-- Error Message -->
          <div v-if="error" class="alert alert-danger" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            {{ error }}
          </div>

          <!-- Contact Form -->
          <form v-if="!submitted" @submit.prevent="submitForm" novalidate>
            <!-- Name Field -->
            <div class="form-group">
              <label for="attendeeName" class="form-label required">
                {{ $t('Your Name') }}
              </label>
              <input
                id="attendeeName"
                v-model="form.attendee_name"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': errors.attendee_name }"
                :placeholder="$t('Enter your full name')"
                required
                autocomplete="name"
              />
              <div v-if="errors.attendee_name" class="invalid-feedback">
                {{ errors.attendee_name[0] }}
              </div>
            </div>

            <!-- Email Field -->
            <div class="form-group">
              <label for="attendeeEmail" class="form-label required">
                {{ $t('Your Email') }}
              </label>
              <input
                id="attendeeEmail"
                v-model="form.attendee_email"
                type="email"
                class="form-control"
                :class="{ 'is-invalid': errors.attendee_email }"
                :placeholder="$t('your.email@example.com')"
                required
                autocomplete="email"
              />
              <div v-if="errors.attendee_email" class="invalid-feedback">
                {{ errors.attendee_email[0] }}
              </div>
            </div>

            <!-- Subject Field -->
            <div class="form-group">
              <label for="subject" class="form-label required">
                {{ $t('Subject') }}
              </label>
              <input
                id="subject"
                v-model="form.subject"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': errors.subject }"
                :placeholder="$t('What is this about?')"
                required
              />
              <div v-if="errors.subject" class="invalid-feedback">
                {{ errors.subject[0] }}
              </div>
            </div>

            <!-- Message Field -->
            <div class="form-group">
              <label for="message" class="form-label required">
                {{ $t('Message') }}
              </label>
              <textarea
                id="message"
                v-model="form.message"
                class="form-control"
                :class="{ 'is-invalid': errors.message }"
                rows="5"
                :placeholder="$t('Type your message here...')"
                required
              ></textarea>
              <div v-if="errors.message" class="invalid-feedback">
                {{ errors.message[0] }}
              </div>
              <small class="form-text text-muted">
                {{ $t('Minimum 10 characters') }} ({{ form.message.length }}/500)
              </small>
            </div>

            <!-- Additional Fields (if configured) -->
            <div 
              v-for="field in additionalFields" 
              :key="field.name"
              class="form-group"
            >
              <label :for="field.name" class="form-label" :class="{ required: field.required }">
                {{ field.label }}
              </label>
              
              <!-- Text Input -->
              <input
                v-if="field.type === 'text'"
                :id="field.name"
                v-model="form.additional_data[field.name]"
                type="text"
                class="form-control"
                :placeholder="field.placeholder"
                :required="field.required"
              />
              
              <!-- Select Dropdown -->
              <select
                v-else-if="field.type === 'select'"
                :id="field.name"
                v-model="form.additional_data[field.name]"
                class="form-control"
                :required="field.required"
              >
                <option value="">{{ $t('Please select...') }}</option>
                <option 
                  v-for="option in field.options" 
                  :key="option.value" 
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
              
              <!-- Textarea -->
              <textarea
                v-else-if="field.type === 'textarea'"
                :id="field.name"
                v-model="form.additional_data[field.name]"
                class="form-control"
                :rows="field.rows || 3"
                :placeholder="field.placeholder"
                :required="field.required"
              ></textarea>
            </div>

            <!-- Privacy Notice -->
            <div class="privacy-notice">
              <small class="text-muted">
                <i class="fas fa-shield-alt me-1"></i>
                {{ $t('Your contact information will only be shared with this exhibitor and will not be used for any other purposes.') }}
              </small>
            </div>
          </form>
        </div>

        <!-- Modal Footer -->
        <div class="modal-footer">
          <button 
            type="button" 
            class="btn btn-secondary" 
            @click="closeModal"
            :disabled="loading"
          >
            {{ submitted ? $t('Close') : $t('Cancel') }}
          </button>
          
          <button 
            v-if="!submitted"
            type="submit" 
            class="btn btn-primary" 
            @click="submitForm"
            :disabled="loading || !isFormValid"
          >
            <span v-if="loading" class="spinner-border spinner-border-sm me-2" role="status">
              <span class="sr-only">{{ $t('Sending...') }}</span>
            </span>
            <i v-else class="fas fa-paper-plane me-2"></i>
            {{ loading ? $t('Sending...') : $t('Send Message') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useExhibitorStore } from '../store/exhibitors'

// Props
const props = defineProps({
  exhibitor: {
    type: Object,
    default: null
  },
  show: {
    type: Boolean,
    default: false
  },
  additionalFields: {
    type: Array,
    default: () => []
  }
})

// Emits
const emit = defineEmits(['close', 'submitted'])

// Composables
const exhibitorStore = useExhibitorStore()

// Reactive data
const loading = ref(false)
const submitted = ref(false)
const error = ref(null)
const errors = ref({})

const form = ref({
  attendee_name: '',
  attendee_email: '',
  subject: '',
  message: '',
  additional_data: {}
})

// Computed properties
const isFormValid = computed(() => {
  return (
    form.value.attendee_name.trim().length >= 2 &&
    form.value.attendee_email.includes('@') &&
    form.value.subject.trim().length >= 3 &&
    form.value.message.trim().length >= 10
  )
})

// Methods
const resetForm = () => {
  form.value = {
    attendee_name: '',
    attendee_email: '',
    subject: '',
    message: '',
    additional_data: {}
  }
  errors.value = {}
  error.value = null
  submitted.value = false
  loading.value = false
}

const closeModal = () => {
  if (!loading.value) {
    emit('close')
  }
}

const validateForm = () => {
  const newErrors = {}
  
  // Name validation
  if (!form.value.attendee_name.trim()) {
    newErrors.attendee_name = ['Name is required']
  } else if (form.value.attendee_name.trim().length < 2) {
    newErrors.attendee_name = ['Name must be at least 2 characters long']
  }
  
  // Email validation
  if (!form.value.attendee_email.trim()) {
    newErrors.attendee_email = ['Email is required']
  } else if (!form.value.attendee_email.includes('@')) {
    newErrors.attendee_email = ['Please enter a valid email address']
  }
  
  // Subject validation
  if (!form.value.subject.trim()) {
    newErrors.subject = ['Subject is required']
  } else if (form.value.subject.trim().length < 3) {
    newErrors.subject = ['Subject must be at least 3 characters long']
  }
  
  // Message validation
  if (!form.value.message.trim()) {
    newErrors.message = ['Message is required']
  } else if (form.value.message.trim().length < 10) {
    newErrors.message = ['Message must be at least 10 characters long']
  } else if (form.value.message.length > 500) {
    newErrors.message = ['Message must be less than 500 characters']
  }
  
  // Additional fields validation
  props.additionalFields.forEach(field => {
    if (field.required && !form.value.additional_data[field.name]) {
      newErrors[field.name] = [`${field.label} is required`]
    }
  })
  
  errors.value = newErrors
  return Object.keys(newErrors).length === 0
}

const submitForm = async () => {
  if (!validateForm()) {
    return
  }
  
  loading.value = true
  error.value = null
  
  try {
    await exhibitorStore.submitContactRequest(props.exhibitor.id, {
      ...form.value,
      attendee_name: form.value.attendee_name.trim(),
      attendee_email: form.value.attendee_email.trim().toLowerCase(),
      subject: form.value.subject.trim(),
      message: form.value.message.trim()
    })
    
    submitted.value = true
    emit('submitted')
    
    // Auto-close after 3 seconds
    setTimeout(() => {
      if (submitted.value) {
        closeModal()
      }
    }, 3000)
    
  } catch (err) {
    if (err.response?.data?.errors) {
      errors.value = err.response.data.errors
    } else {
      error.value = err.message || 'Failed to send message. Please try again.'
    }
  } finally {
    loading.value = false
  }
}

// Watchers
watch(() => props.show, (newVal) => {
  if (newVal) {
    resetForm()
    // Focus on first input when modal opens
    nextTick(() => {
      const firstInput = document.getElementById('attendeeName')
      if (firstInput) {
        firstInput.focus()
      }
    })
  }
})

// Handle escape key
watch(() => props.show, (newVal) => {
  const handleEscape = (e) => {
    if (e.key === 'Escape') {
      closeModal()
    }
  }
  
  if (newVal) {
    document.addEventListener('keydown', handleEscape)
  } else {
    document.removeEventListener('keydown', handleEscape)
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
  padding: 1rem;
  backdrop-filter: blur(4px);
}

.modal-dialog {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  width: 100%;
  max-width: 600px;
  max-height: 90vh;
  overflow: hidden;
  animation: modalSlideIn 0.3s ease-out;
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-50px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid #e9ecef;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f8f9fa;
}

.modal-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.25rem;
  color: #6c757d;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.btn-close:hover {
  background: #e9ecef;
  color: #495057;
}

.modal-body {
  padding: 1.5rem;
  flex: 1;
  overflow-y: auto;
}

.modal-description {
  color: #6c757d;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
}

.form-group {
  margin-bottom: 1.25rem;
}

.form-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #333;
}

.form-label.required::after {
  content: ' *';
  color: #dc3545;
}

.form-control {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.form-control:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.form-control.is-invalid {
  border-color: #dc3545;
}

.form-control.is-invalid:focus {
  box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.1);
}

.invalid-feedback {
  display: block;
  color: #dc3545;
  font-size: 0.85rem;
  margin-top: 0.25rem;
}

.form-text {
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.privacy-notice {
  margin-top: 1.5rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #007bff;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e9ecef;
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  background: #f8f9fa;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #5a6268;
}

.btn-primary {
  background: linear-gradient(135deg, #007bff, #0056b3);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #0056b3, #004085);
  transform: translateY(-1px);
}

.alert {
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.alert-success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.alert-danger {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.spinner-border-sm {
  width: 1rem;
  height: 1rem;
  border-width: 0.125rem;
}

/* Responsive Design */
@media (max-width: 768px) {
  .modal-overlay {
    padding: 0.5rem;
  }
  
  .modal-dialog {
    max-height: 95vh;
  }
  
  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem;
  }
  
  .modal-footer {
    flex-direction: column;
  }
  
  .btn {
    width: 100%;
    justify-content: center;
  }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .modal-dialog {
    background: #2d3748;
    color: #e2e8f0;
  }
  
  .modal-header {
    background: #4a5568;
    border-color: #4a5568;
  }
  
  .modal-footer {
    background: #4a5568;
    border-color: #4a5568;
  }
  
  .form-control {
    background: #4a5568;
    border-color: #718096;
    color: #e2e8f0;
  }
  
  .form-control:focus {
    border-color: #63b3ed;
  }
  
  .privacy-notice {
    background: #4a5568;
    border-color: #63b3ed;
  }
}
</style>