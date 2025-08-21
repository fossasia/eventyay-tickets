<template>
  <div class="exhibitor-detail">
    <!-- Loading State -->
    <div v-if="loading" class="loading-container">
      <div class="spinner-border" role="status">
        <span class="sr-only">{{ $t('Loading...') }}</span>
      </div>
      <p class="mt-3">{{ $t('Loading exhibitor details...') }}</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="alert alert-danger" role="alert">
      <i class="fas fa-exclamation-triangle me-2"></i>
      {{ error }}
      <button class="btn btn-sm btn-outline-danger ms-2" @click="fetchExhibitorData">
        {{ $t('Retry') }}
      </button>
    </div>

    <!-- Exhibitor Content -->
    <div v-else-if="exhibitor" class="exhibitor-content">
      <!-- Header Section -->
      <div class="exhibitor-header">
        <!-- Banner/Video Section -->
        <div v-if="exhibitor.banner_url" class="banner-section">
          <video 
            v-if="bannerIsVideo" 
            class="banner-video" 
            :poster="exhibitor.logo_url"
            controls
            preload="metadata"
          >
            <source :src="exhibitor.banner_url" type="video/mp4">
            <p>{{ $t('Your browser does not support the video tag.') }}</p>
          </video>
          <img 
            v-else 
            :src="exhibitor.banner_url" 
            :alt="exhibitor.name + ' banner'"
            class="banner-image"
            @error="onImageError"
          />
        </div>

        <!-- Header Info -->
        <div class="header-info">
          <div class="exhibitor-logo">
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
          
          <div class="exhibitor-meta">
            <h1 class="exhibitor-name">{{ exhibitor.name }}</h1>
            <p v-if="exhibitor.tagline" class="exhibitor-tagline">{{ exhibitor.tagline }}</p>
            <div class="booth-info">
              <span class="booth-badge">
                <i class="fas fa-map-marker-alt"></i>
                {{ exhibitor.booth_name || exhibitor.booth_id }}
              </span>
              <span v-if="exhibitor.featured" class="featured-badge">
                <i class="fas fa-star"></i>
                {{ $t('Featured') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="main-content">
        <div class="row">
          <!-- Left Column - Main Info -->
          <div class="col-lg-8">
            <!-- Description -->
            <div v-if="exhibitor.description" class="content-section">
              <h3>{{ $t('About') }}</h3>
              <div class="description-content" v-html="formattedDescription"></div>
            </div>

            <!-- Downloads Section -->
            <div v-if="downloadLinks.length > 0" class="content-section">
              <h3>{{ $t('Downloads') }}</h3>
              <div class="downloads-grid">
                <a 
                  v-for="link in downloadLinks" 
                  :key="link.id"
                  :href="link.url" 
                  target="_blank"
                  rel="noopener noreferrer"
                  class="download-item"
                >
                  <i class="fas fa-download"></i>
                  <span>{{ link.display_text }}</span>
                </a>
              </div>
            </div>

            <!-- External Links -->
            <div v-if="externalLinks.length > 0" class="content-section">
              <h3>{{ $t('Links') }}</h3>
              <div class="external-links">
                <a 
                  v-for="link in externalLinks" 
                  :key="link.id"
                  :href="link.url" 
                  target="_blank"
                  rel="noopener noreferrer"
                  class="external-link"
                >
                  <i class="fas fa-external-link-alt"></i>
                  <span>{{ link.display_text }}</span>
                </a>
              </div>
            </div>
          </div>

          <!-- Right Column - Sidebar -->
          <div class="col-lg-4">
            <!-- Contact Section -->
            <div class="sidebar-section">
              <h4>{{ $t('Contact') }}</h4>
              <div class="contact-actions">
                <button 
                  v-if="exhibitor.contact_enabled"
                  class="btn btn-primary btn-block"
                  @click="openContactModal"
                >
                  <i class="fas fa-envelope"></i>
                  {{ $t('Send Message') }}
                </button>
                
                <a 
                  v-if="exhibitor.url"
                  :href="exhibitor.url" 
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline-primary btn-block"
                >
                  <i class="fas fa-globe"></i>
                  {{ $t('Visit Website') }}
                </a>
              </div>
            </div>

            <!-- Social Media Links -->
            <div v-if="socialLinks.length > 0" class="sidebar-section">
              <h4>{{ $t('Follow Us') }}</h4>
              <div class="social-links">
                <a 
                  v-for="link in socialLinks" 
                  :key="link.id"
                  :href="link.url" 
                  target="_blank"
                  rel="noopener noreferrer"
                  class="social-link"
                  :title="link.display_text"
                >
                  <i :class="getSocialIcon(link.url)"></i>
                </a>
              </div>
            </div>

            <!-- Virtual Booth -->
            <div v-if="exhibitor.highlighted_room_id" class="sidebar-section">
              <h4>{{ $t('Virtual Booth') }}</h4>
              <button class="btn btn-success btn-block" @click="joinVirtualBooth">
                <i class="fas fa-video"></i>
                {{ $t('Join Virtual Booth') }}
              </button>
            </div>

            <!-- Staff Section -->
            <div v-if="staff.length > 0" class="sidebar-section">
              <h4>{{ $t('Meet the Team') }}</h4>
              <div class="staff-list">
                <div v-for="member in staff" :key="member.id" class="staff-member">
                  <div class="staff-avatar">
                    <img 
                      v-if="member.user.avatar"
                      :src="member.user.avatar" 
                      :alt="member.user.name"
                      class="avatar-image"
                    />
                    <div v-else class="avatar-placeholder">
                      <i class="fas fa-user"></i>
                    </div>
                  </div>
                  <div class="staff-info">
                    <h6 class="staff-name">{{ member.user.name }}</h6>
                    <p class="staff-role">{{ member.role }}</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tags -->
            <div v-if="tags.length > 0" class="sidebar-section">
              <h4>{{ $t('Tags') }}</h4>
              <div class="tags-list">
                <span 
                  v-for="tag in tags" 
                  :key="tag.id"
                  class="tag-badge"
                >
                  {{ tag.name }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Contact Modal -->
    <ContactModal
      v-if="selectedExhibitor"
      :exhibitor="selectedExhibitor"
      :show="showContactModal"
      @close="closeContactModal"
      @submitted="onContactSubmitted"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useExhibitorStore } from '../store/exhibitors'
import ContactModal from '../components/ContactModal.vue'

// Composables
const route = useRoute()
const router = useRouter()
const exhibitorStore = useExhibitorStore()

// Reactive data
const exhibitor = ref(null)
const loading = ref(false)
const error = ref(null)
const selectedExhibitor = ref(null)
const showContactModal = ref(false)
const imageErrors = ref(new Set())

// Computed properties
const bannerIsVideo = computed(() => {
  if (!exhibitor.value?.banner_url) return false
  return exhibitor.value.banner_url.toLowerCase().match(/\.(mp4|webm|mov)$/)
})

const formattedDescription = computed(() => {
  if (!exhibitor.value?.description) return ''
  // Simple HTML formatting - in production, use a proper sanitizer
  return exhibitor.value.description.replace(/\n/g, '<br>')
})

const socialLinks = computed(() => {
  return exhibitor.value?.links?.filter(link => link.category === 'social') || []
})

const downloadLinks = computed(() => {
  return exhibitor.value?.links?.filter(link => link.category === 'download') || []
})

const externalLinks = computed(() => {
  return exhibitor.value?.links?.filter(link => 
    ['external', 'profile', 'video'].includes(link.category)
  ) || []
})

const staff = computed(() => {
  return exhibitor.value?.staff || []
})

const tags = computed(() => {
  return exhibitor.value?.tags || []
})

// Methods
const fetchExhibitorData = async () => {
  const boothId = route.params.booth_id
  if (!boothId) {
    error.value = 'No booth ID provided'
    return
  }

  loading.value = true
  error.value = null

  try {
    exhibitor.value = await exhibitorStore.fetchExhibitorByBoothId(boothId)
    if (!exhibitor.value) {
      error.value = 'Exhibitor not found'
    }
  } catch (err) {
    error.value = err.message || 'Failed to load exhibitor details'
  } finally {
    loading.value = false
  }
}

const openContactModal = () => {
  selectedExhibitor.value = exhibitor.value
  showContactModal.value = true
}

const closeContactModal = () => {
  showContactModal.value = false
  selectedExhibitor.value = null
}

const onContactSubmitted = () => {
  // Handle successful contact submission
  closeContactModal()
  // Could show a success message here
}

const joinVirtualBooth = () => {
  if (exhibitor.value?.highlighted_room_id) {
    // Navigate to video room - adjust URL as needed
    window.open(`/video/room/${exhibitor.value.highlighted_room_id}`, '_blank')
  }
}

const getSocialIcon = (url) => {
  const domain = new URL(url).hostname.toLowerCase()
  if (domain.includes('facebook')) return 'fab fa-facebook'
  if (domain.includes('twitter')) return 'fab fa-twitter'
  if (domain.includes('linkedin')) return 'fab fa-linkedin'
  if (domain.includes('instagram')) return 'fab fa-instagram'
  if (domain.includes('youtube')) return 'fab fa-youtube'
  return 'fas fa-link'
}

const onImageError = (event) => {
  const src = event.target.src
  imageErrors.value.add(src)
  event.target.style.display = 'none'
}

// Lifecycle
onMounted(() => {
  fetchExhibitorData()
})

// Watch for route changes
watch(() => route.params.booth_id, () => {
  if (route.params.booth_id) {
    fetchExhibitorData()
  }
})
</script>

<style scoped>
.exhibitor-detail {
  min-height: 100vh;
  background: #f8f9fa;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.exhibitor-header {
  background: white;
  margin-bottom: 2rem;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.banner-section {
  position: relative;
  height: 300px;
  overflow: hidden;
}

.banner-image,
.banner-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.header-info {
  padding: 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.exhibitor-logo {
  flex-shrink: 0;
}

.logo-image {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  object-fit: cover;
  border: 3px solid white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.logo-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 12px;
  background: #e9ecef;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2rem;
  color: #6c757d;
}

.exhibitor-name {
  font-size: 2rem;
  font-weight: 700;
  margin: 0;
  color: #2c3e50;
}

.exhibitor-tagline {
  font-size: 1.1rem;
  color: #6c757d;
  margin: 0.5rem 0;
}

.booth-info {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.booth-badge,
.featured-badge {
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.booth-badge {
  background: #e3f2fd;
  color: #1976d2;
}

.featured-badge {
  background: #fff3e0;
  color: #f57c00;
}

.main-content {
  gap: 2rem;
}

.content-section {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  margin-bottom: 2rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.content-section h3 {
  font-size: 1.5rem;
  font-weight: 600;
  margin-bottom: 1.5rem;
  color: #2c3e50;
}

.description-content {
  line-height: 1.6;
  color: #495057;
}

.downloads-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.download-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
  text-decoration: none;
  color: #495057;
  transition: all 0.3s ease;
}

.download-item:hover {
  background: #e9ecef;
  transform: translateY(-2px);
}

.external-links {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.external-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: #f8f9fa;
  border-radius: 8px;
  text-decoration: none;
  color: #495057;
  transition: all 0.3s ease;
}

.external-link:hover {
  background: #e9ecef;
}

.sidebar-section {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.sidebar-section h4 {
  font-size: 1.2rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #2c3e50;
}

.contact-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.btn-block {
  width: 100%;
}

.social-links {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.social-link {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f8f9fa;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #495057;
  text-decoration: none;
  transition: all 0.3s ease;
}

.social-link:hover {
  background: #007bff;
  color: white;
  transform: translateY(-2px);
}

.staff-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.staff-member {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.staff-avatar {
  flex-shrink: 0;
}

.avatar-image {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: #e9ecef;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.staff-name {
  font-weight: 600;
  margin: 0;
  color: #2c3e50;
}

.staff-role {
  font-size: 0.9rem;
  color: #6c757d;
  margin: 0;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag-badge {
  padding: 0.25rem 0.75rem;
  background: #e9ecef;
  border-radius: 12px;
  font-size: 0.85rem;
  color: #495057;
}

@media (max-width: 768px) {
  .header-info {
    flex-direction: column;
    text-align: center;
  }
  
  .booth-info {
    justify-content: center;
  }
  
  .downloads-grid {
    grid-template-columns: 1fr;
  }
}
</style>