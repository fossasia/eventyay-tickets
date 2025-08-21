<template>
  <div 
    class="exhibitor-card" 
    :class="{ 'featured': exhibitor.featured, 'clickable': clickable }"
    @click="handleClick"
  >
    <!-- Featured Badge -->
    <div v-if="exhibitor.featured" class="featured-badge">
      <i class="fas fa-star"></i>
      <span>{{ $t('Featured') }}</span>
    </div>

    <!-- Card Header with Logo/Banner -->
    <div class="card-header">
      <div v-if="exhibitor.banner_url" class="banner-container">
        <img 
          :src="exhibitor.banner_url" 
          :alt="exhibitor.name + ' banner'"
          class="banner-image"
          @error="onImageError"
        />
        <div class="banner-overlay"></div>
      </div>
      
      <div class="logo-container" :class="{ 'no-banner': !exhibitor.banner_url }">
        <img 
          v-if="exhibitor.logo_url"
          :src="exhibitor.logo_url" 
          :alt="exhibitor.name + ' logo'"
          class="logo-image"
          @error="onImageError"
        />
        <div v-else class="logo-placeholder">
          <i class="fas fa-building"></i>
        </div>
      </div>
    </div>

    <!-- Card Body -->
    <div class="card-body">
      <div class="exhibitor-info">
        <h5 class="exhibitor-name" :title="exhibitor.name">
          {{ exhibitor.name }}
        </h5>
        
        <p v-if="exhibitor.tagline" class="exhibitor-tagline" :title="exhibitor.tagline">
          {{ exhibitor.tagline }}
        </p>
        
        <div class="booth-info">
          <span class="booth-id">
            <i class="fas fa-map-marker-alt"></i>
            {{ exhibitor.booth_name || exhibitor.booth_id }}
          </span>
        </div>
      </div>

      <!-- Stats -->
      <div class="exhibitor-stats">
        <div v-if="exhibitor.staff_count > 0" class="stat-item">
          <i class="fas fa-users"></i>
          <span>{{ exhibitor.staff_count }} {{ $t('staff') }}</span>
        </div>
        
        <div v-if="exhibitor.links_count > 0" class="stat-item">
          <i class="fas fa-link"></i>
          <span>{{ exhibitor.links_count }} {{ $t('links') }}</span>
        </div>
      </div>
    </div>

    <!-- Card Footer -->
    <div class="card-footer">
      <div class="action-buttons">
        <button 
          class="btn btn-primary btn-sm"
          @click.stop="$emit('click', exhibitor)"
          :aria-label="$t('View {name} details', { name: exhibitor.name })"
        >
          <i class="fas fa-eye"></i>
          {{ $t('View Details') }}
        </button>
        
        <button 
          v-if="exhibitor.contact_enabled"
          class="btn btn-outline-secondary btn-sm"
          @click.stop="$emit('contact', exhibitor)"
          :aria-label="$t('Contact {name}', { name: exhibitor.name })"
        >
          <i class="fas fa-envelope"></i>
          {{ $t('Contact') }}
        </button>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="loading-overlay">
      <div class="spinner-border spinner-border-sm" role="status">
        <span class="sr-only">{{ $t('Loading...') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// Props
const props = defineProps({
  exhibitor: {
    type: Object,
    required: true
  },
  clickable: {
    type: Boolean,
    default: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['click', 'contact'])

// Reactive data
const imageErrors = ref(new Set())

// Computed properties
const hasValidLogo = computed(() => {
  return props.exhibitor.logo_url && !imageErrors.value.has(props.exhibitor.logo_url)
})

const hasValidBanner = computed(() => {
  return props.exhibitor.banner_url && !imageErrors.value.has(props.exhibitor.banner_url)
})

// Methods
const handleClick = () => {
  if (props.clickable && !props.loading) {
    emit('click', props.exhibitor)
  }
}

const onImageError = (event) => {
  const src = event.target.src
  imageErrors.value.add(src)
  
  // Hide the broken image
  event.target.style.display = 'none'
}
</script>

<style scoped>
.exhibitor-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  transition: all 0.3s ease;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.exhibitor-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
}

.exhibitor-card.clickable {
  cursor: pointer;
}

.exhibitor-card.featured {
  border: 2px solid #ffd700;
  box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3);
}

.featured-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #ffd700, #ffed4e);
  color: #333;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.card-header {
  position: relative;
  height: 120px;
  overflow: hidden;
}

.banner-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.banner-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.banner-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.3));
}

.logo-container {
  position: absolute;
  bottom: -20px;
  left: 20px;
  width: 60px;
  height: 60px;
  border-radius: 12px;
  overflow: hidden;
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}

.logo-container.no-banner {
  position: static;
  margin: 20px auto 0;
  width: 80px;
  height: 80px;
}

.logo-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 4px;
}

.logo-placeholder {
  color: #6c757d;
  font-size: 1.5rem;
}

.card-body {
  padding: 24px 20px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.exhibitor-info {
  flex: 1;
}

.exhibitor-name {
  font-size: 1.1rem;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px 0;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.exhibitor-tagline {
  font-size: 0.9rem;
  color: #6c757d;
  margin: 0 0 12px 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.booth-info {
  margin-bottom: 12px;
}

.booth-id {
  font-size: 0.85rem;
  color: #495057;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}

.booth-id i {
  color: #007bff;
  font-size: 0.8rem;
}

.exhibitor-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.stat-item {
  font-size: 0.8rem;
  color: #6c757d;
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-item i {
  font-size: 0.75rem;
  opacity: 0.8;
}

.card-footer {
  padding: 0 20px 20px;
  border-top: none;
  background: transparent;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.action-buttons .btn {
  flex: 1;
  font-size: 0.85rem;
  padding: 6px 12px;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.action-buttons .btn i {
  margin-right: 4px;
  font-size: 0.8rem;
}

.btn-primary {
  background: linear-gradient(135deg, #007bff, #0056b3);
  border: none;
}

.btn-primary:hover {
  background: linear-gradient(135deg, #0056b3, #004085);
  transform: translateY(-1px);
}

.btn-outline-secondary {
  border-color: #dee2e6;
  color: #6c757d;
}

.btn-outline-secondary:hover {
  background-color: #f8f9fa;
  border-color: #adb5bd;
  color: #495057;
  transform: translateY(-1px);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}

/* Responsive Design */
@media (max-width: 576px) {
  .card-header {
    height: 100px;
  }
  
  .logo-container {
    width: 50px;
    height: 50px;
    bottom: -15px;
    left: 15px;
  }
  
  .card-body {
    padding: 20px 16px 12px;
  }
  
  .card-footer {
    padding: 0 16px 16px;
  }
  
  .exhibitor-name {
    font-size: 1rem;
  }
  
  .action-buttons {
    flex-direction: column;
  }
  
  .action-buttons .btn {
    font-size: 0.8rem;
  }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .exhibitor-card {
    background: #2d3748;
    color: #e2e8f0;
  }
  
  .exhibitor-name {
    color: #f7fafc;
  }
  
  .exhibitor-tagline {
    color: #a0aec0;
  }
  
  .booth-id {
    color: #cbd5e0;
  }
  
  .stat-item {
    color: #a0aec0;
  }
  
  .logo-container {
    background: #4a5568;
  }
}

/* Animation for card entrance */
@keyframes cardEntrance {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.exhibitor-card {
  animation: cardEntrance 0.5s ease-out;
}
</style>