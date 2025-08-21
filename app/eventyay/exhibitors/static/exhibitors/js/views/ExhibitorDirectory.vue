<template>
  <div class="exhibitor-directory">
    <!-- Page Header -->
    <div class="page-header">
      <div class="container">
        <div class="row align-items-center">
          <div class="col-lg-8">
            <h1 class="page-title">
              <i class="fas fa-store me-3"></i>
              {{ $t('Exhibitor Directory') }}
            </h1>
            <p class="page-subtitle">
              {{ $t('Discover amazing exhibitors and connect with industry leaders') }}
            </p>
          </div>
          <div class="col-lg-4 text-lg-end">
            <div class="header-stats">
              <div class="stat-item">
                <span class="stat-number">{{ totalExhibitors }}</span>
                <span class="stat-label">{{ $t('Exhibitors') }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-number">{{ featuredCount }}</span>
                <span class="stat-label">{{ $t('Featured') }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Filters and Search -->
    <div class="filters-section">
      <div class="container">
        <div class="filters-card">
          <div class="row align-items-center">
            <!-- Search -->
            <div class="col-lg-4 col-md-6">
              <div class="search-box">
                <i class="fas fa-search search-icon"></i>
                <input
                  v-model="searchQuery"
                  type="text"
                  class="form-control search-input"
                  :placeholder="$t('Search exhibitors, booths, or keywords...')"
                  @input="debouncedSearch"
                />
                <button 
                  v-if="searchQuery" 
                  class="clear-search"
                  @click="clearSearch"
                  :aria-label="$t('Clear search')"
                >
                  <i class="fas fa-times"></i>
                </button>
              </div>
            </div>

            <!-- Sort -->
            <div class="col-lg-2 col-md-3">
              <select v-model="sortBy" class="form-select" @change="applyFilters">
                <option value="sort_order">{{ $t('Default Order') }}</option>
                <option value="name">{{ $t('Name A-Z') }}</option>
                <option value="featured">{{ $t('Featured First') }}</option>
                <option value="created_at">{{ $t('Newest First') }}</option>
              </select>
            </div>

            <!-- Featured Filter -->
            <div class="col-lg-2 col-md-3">
              <div class="form-check form-switch">
                <input
                  id="featuredOnly"
                  v-model="featuredOnly"
                  type="checkbox"
                  class="form-check-input"
                  @change="applyFilters"
                />
                <label for="featuredOnly" class="form-check-label">
                  {{ $t('Featured Only') }}
                </label>
              </div>
            </div>

            <!-- View Toggle -->
            <div class="col-lg-2 col-md-6">
              <div class="view-toggle">
                <button 
                  class="btn btn-outline-secondary"
                  :class="{ active: viewMode === 'grid' }"
                  @click="viewMode = 'grid'"
                  :aria-label="$t('Grid view')"
                >
                  <i class="fas fa-th"></i>
                </button>
                <button 
                  class="btn btn-outline-secondary"
                  :class="{ active: viewMode === 'list' }"
                  @click="viewMode = 'list'"
                  :aria-label="$t('List view')"
                >
                  <i class="fas fa-list"></i>
                </button>
              </div>
            </div>

            <!-- Results Count -->
            <div class="col-lg-2 col-md-6">
              <div class="results-count">
                <small class="text-muted">
                  {{ $t('{count} results', { count: filteredExhibitors.length }) }}
                </small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
      <div class="container">
        <div class="row">
          <!-- Sidebar -->
          <div class="col-lg-3">
            <div class="sidebar">
              <!-- Featured Exhibitors -->
              <div v-if="featuredExhibitors.length > 0" class="sidebar-section">
                <h4 class="sidebar-title">
                  <i class="fas fa-star me-2"></i>
                  {{ $t('Featured Exhibitors') }}
                </h4>
                <div class="featured-list">
                  <div 
                    v-for="exhibitor in featuredExhibitors.slice(0, 5)" 
                    :key="exhibitor.id"
                    class="featured-item"
                    @click="viewExhibitor(exhibitor)"
                  >
                    <div class="featured-logo">
                      <img 
                        v-if="exhibitor.logo_url"
                        :src="exhibitor.logo_url" 
                        :alt="exhibitor.name"
                        class="logo-image"
                      />
                      <div v-else class="logo-placeholder">
                        <i class="fas fa-building"></i>
                      </div>
                    </div>
                    <div class="featured-info">
                      <h6 class="featured-name">{{ exhibitor.name }}</h6>
                      <p class="featured-booth">{{ exhibitor.booth_name }}</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Tags Filter -->
              <div v-if="availableTags.length > 0" class="sidebar-section">
                <h4 class="sidebar-title">
                  <i class="fas fa-tags me-2"></i>
                  {{ $t('Filter by Tags') }}
                </h4>
                <div class="tags-filter">
                  <button
                    v-for="tag in availableTags.slice(0, 10)"
                    :key="tag"
                    class="tag-filter-btn"
                    :class="{ active: selectedTags.includes(tag) }"
                    @click="toggleTag(tag)"
                  >
                    {{ tag }}
                  </button>
                </div>
              </div>

              <!-- Quick Stats -->
              <div class="sidebar-section">
                <h4 class="sidebar-title">
                  <i class="fas fa-chart-bar me-2"></i>
                  {{ $t('Quick Stats') }}
                </h4>
                <div class="quick-stats">
                  <div class="stat-row">
                    <span class="stat-label">{{ $t('Total Exhibitors') }}</span>
                    <span class="stat-value">{{ totalExhibitors }}</span>
                  </div>
                  <div class="stat-row">
                    <span class="stat-label">{{ $t('Featured') }}</span>
                    <span class="stat-value">{{ featuredCount }}</span>
                  </div>
                  <div class="stat-row">
                    <span class="stat-label">{{ $t('With Virtual Booths') }}</span>
                    <span class="stat-value">{{ virtualBoothCount }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Exhibitor List -->
          <div class="col-lg-9">
            <!-- Loading State -->
            <div v-if="loading" class="loading-state">
              <div class="text-center py-5">
                <div class="spinner-border spinner-border-lg" role="status">
                  <span class="sr-only">{{ $t('Loading...') }}</span>
                </div>
                <p class="mt-3">{{ $t('Loading exhibitors...') }}</p>
              </div>
            </div>

            <!-- Error State -->
            <div v-else-if="error" class="error-state">
              <div class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                {{ error }}
                <button class="btn btn-sm btn-outline-danger ms-2" @click="fetchExhibitors">
                  {{ $t('Retry') }}
                </button>
              </div>
            </div>

            <!-- Empty State -->
            <div v-else-if="filteredExhibitors.length === 0" class="empty-state">
              <div class="text-center py-5">
                <i class="fas fa-store fa-4x text-muted mb-4"></i>
                <h4 class="text-muted">{{ $t('No exhibitors found') }}</h4>
                <p class="text-muted mb-4">
                  {{ searchQuery ? 
                    $t('Try adjusting your search criteria or filters') : 
                    $t('No exhibitors are currently available') 
                  }}
                </p>
                <button 
                  v-if="searchQuery || selectedTags.length > 0 || featuredOnly" 
                  class="btn btn-primary"
                  @click="clearAllFilters"
                >
                  {{ $t('Clear All Filters') }}
                </button>
              </div>
            </div>

            <!-- Exhibitor Grid/List -->
            <div v-else class="exhibitor-results">
              <!-- Grid View -->
              <div v-if="viewMode === 'grid'" class="exhibitor-grid">
                <div class="row">
                  <div
                    v-for="exhibitor in paginatedExhibitors"
                    :key="exhibitor.id"
                    class="col-xl-4 col-lg-6 col-md-6 col-sm-12 mb-4"
                  >
                    <ExhibitorCard
                      :exhibitor="exhibitor"
                      @click="viewExhibitor(exhibitor)"
                      @contact="openContactModal(exhibitor)"
                    />
                  </div>
                </div>
              </div>

              <!-- List View -->
              <div v-else class="exhibitor-list-view">
                <div 
                  v-for="exhibitor in paginatedExhibitors"
                  :key="exhibitor.id"
                  class="exhibitor-list-item"
                  @click="viewExhibitor(exhibitor)"
                >
                  <div class="list-item-content">
                    <div class="list-item-logo">
                      <img 
                        v-if="exhibitor.logo_url"
                        :src="exhibitor.logo_url" 
                        :alt="exhibitor.name"
                        class="logo-image"
                      />
                      <div v-else class="logo-placeholder">
                        <i class="fas fa-building"></i>
                      </div>
                    </div>
                    <div class="list-item-info">
                      <div class="list-item-header">
                        <h5 class="exhibitor-name">{{ exhibitor.name }}</h5>
                        <div class="exhibitor-badges">
                          <span v-if="exhibitor.featured" class="badge badge-featured">
                            <i class="fas fa-star"></i> {{ $t('Featured') }}
                          </span>
                          <span class="badge badge-booth">
                            <i class="fas fa-map-marker-alt"></i> {{ exhibitor.booth_name }}
                          </span>
                        </div>
                      </div>
                      <p v-if="exhibitor.tagline" class="exhibitor-tagline">{{ exhibitor.tagline }}</p>
                      <p v-if="exhibitor.description" class="exhibitor-description">
                        {{ truncateText(exhibitor.description, 150) }}
                      </p>
                    </div>
                    <div class="list-item-actions">
                      <button class="btn btn-primary btn-sm" @click.stop="viewExhibitor(exhibitor)">
                        <i class="fas fa-eye"></i> {{ $t('View') }}
                      </button>
                      <button 
                        v-if="exhibitor.contact_enabled"
                        class="btn btn-outline-secondary btn-sm"
                        @click.stop="openContactModal(exhibitor)"
                      >
                        <i class="fas fa-envelope"></i> {{ $t('Contact') }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Pagination -->
              <nav v-if="totalPages > 1" class="pagination-nav" aria-label="Exhibitor pagination">
                <ul class="pagination justify-content-center">
                  <li class="page-item" :class="{ disabled: currentPage === 1 }">
                    <button class="page-link" @click="goToPage(currentPage - 1)" :disabled="currentPage === 1">
                      <i class="fas fa-chevron-left"></i>
                    </button>
                  </li>
                  
                  <li
                    v-for="page in visiblePages"
                    :key="page"
                    class="page-item"
                    :class="{ active: page === currentPage }"
                  >
                    <button class="page-link" @click="goToPage(page)">
                      {{ page }}
                    </button>
                  </li>
                  
                  <li class="page-item" :class="{ disabled: currentPage === totalPages }">
                    <button class="page-link" @click="goToPage(currentPage + 1)" :disabled="currentPage === totalPages">
                      <i class="fas fa-chevron-right"></i>
                    </button>
                  </li>
                </ul>
              </nav>

              <!-- Results Info -->
              <div class="results-info text-center mt-4">
                <small class="text-muted">
                  {{ $t('Showing {start} to {end} of {total} exhibitors', {
                    start: (currentPage - 1) * itemsPerPage + 1,
                    end: Math.min(currentPage * itemsPerPage, filteredExhibitors.length),
                    total: filteredExhibitors.length
                  }) }}
                </small>
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
import { useRouter } from 'vue-router'
import { useExhibitorStore } from '../store/exhibitors'
import ExhibitorCard from '../components/ExhibitorCard.vue'
import ContactModal from '../components/ContactModal.vue'

// Simple debounce function
function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

// Props
const props = defineProps({
  eventId: {
    type: [String, Number],
    default: null
  }
})

// Composables
const router = useRouter()
const exhibitorStore = useExhibitorStore()

// Reactive data
const searchQuery = ref('')
const sortBy = ref('sort_order')
const featuredOnly = ref(false)
const selectedTags = ref([])
const viewMode = ref('grid')
const currentPage = ref(1)
const itemsPerPage = ref(12)
const loading = ref(false)
const error = ref(null)
const selectedExhibitor = ref(null)
const showContactModal = ref(false)

// Computed properties
const filteredExhibitors = computed(() => {
  let exhibitors = [...exhibitorStore.exhibitors]
  
  // Apply search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    exhibitors = exhibitors.filter(exhibitor => 
      exhibitor.name.toLowerCase().includes(query) ||
      exhibitor.tagline?.toLowerCase().includes(query) ||
      exhibitor.booth_name?.toLowerCase().includes(query) ||
      exhibitor.description?.toLowerCase().includes(query)
    )
  }
  
  // Apply featured filter
  if (featuredOnly.value) {
    exhibitors = exhibitors.filter(exhibitor => exhibitor.featured)
  }
  
  // Apply tag filters
  if (selectedTags.value.length > 0) {
    exhibitors = exhibitors.filter(exhibitor => 
      exhibitor.tags?.some(tag => selectedTags.value.includes(tag.name))
    )
  }
  
  // Apply sorting
  switch (sortBy.value) {
    case 'name':
      exhibitors.sort((a, b) => a.name.localeCompare(b.name))
      break
    case 'featured':
      exhibitors.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
      break
    case 'created_at':
      exhibitors.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      break
    default:
      exhibitors.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))
  }
  
  return exhibitors
})

const paginatedExhibitors = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage.value
  const end = start + itemsPerPage.value
  return filteredExhibitors.value.slice(start, end)
})

const totalPages = computed(() => {
  return Math.ceil(filteredExhibitors.value.length / itemsPerPage.value)
})

const visiblePages = computed(() => {
  const pages = []
  const total = totalPages.value
  const current = currentPage.value
  
  if (total <= 7) {
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    if (current <= 4) {
      for (let i = 1; i <= 5; i++) pages.push(i)
      pages.push('...', total)
    } else if (current >= total - 3) {
      pages.push(1, '...')
      for (let i = total - 4; i <= total; i++) pages.push(i)
    } else {
      pages.push(1, '...', current - 1, current, current + 1, '...', total)
    }
  }
  
  return pages.filter(page => page !== '...' || pages.indexOf(page) === pages.lastIndexOf(page))
})

const totalExhibitors = computed(() => exhibitorStore.exhibitors.length)
const featuredCount = computed(() => exhibitorStore.exhibitors.filter(e => e.featured).length)
const virtualBoothCount = computed(() => exhibitorStore.exhibitors.filter(e => e.highlighted_room_id).length)

const featuredExhibitors = computed(() => {
  return exhibitorStore.exhibitors.filter(e => e.featured).slice(0, 6)
})

const availableTags = computed(() => {
  const tags = new Set()
  exhibitorStore.exhibitors.forEach(exhibitor => {
    exhibitor.tags?.forEach(tag => tags.add(tag.name))
  })
  return Array.from(tags).sort()
})

// Methods
const fetchExhibitors = async () => {
  loading.value = true
  error.value = null
  
  try {
    await exhibitorStore.fetchExhibitors({ event_id: props.eventId })
  } catch (err) {
    error.value = err.message || 'Failed to load exhibitors'
  } finally {
    loading.value = false
  }
}

const debouncedSearch = debounce(() => {
  currentPage.value = 1
  applyFilters()
}, 300)

const applyFilters = () => {
  currentPage.value = 1
  // Filters are applied automatically through computed properties
}

const clearSearch = () => {
  searchQuery.value = ''
  applyFilters()
}

const clearAllFilters = () => {
  searchQuery.value = ''
  featuredOnly.value = false
  selectedTags.value = []
  sortBy.value = 'sort_order'
  applyFilters()
}

const toggleTag = (tag) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tag)
  }
  applyFilters()
}

const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    // Scroll to top of results
    document.querySelector('.exhibitor-results')?.scrollIntoView({ behavior: 'smooth' })
  }
}

const viewExhibitor = (exhibitor) => {
  router.push({ name: 'exhibitors:detail', params: { booth_id: exhibitor.booth_id } })
}

const openContactModal = (exhibitor) => {
  selectedExhibitor.value = exhibitor
  showContactModal.value = true
}

const closeContactModal = () => {
  showContactModal.value = false
  selectedExhibitor.value = null
}

const onContactSubmitted = () => {
  closeContactModal()
  // Could show a success message here
}

const truncateText = (text, maxLength) => {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength).trim() + '...'
}

// Lifecycle
onMounted(() => {
  fetchExhibitors()
})

// Watch for prop changes
watch(() => props.eventId, () => {
  if (props.eventId) {
    fetchExhibitors()
  }
})
</script>

<style scoped>
.exhibitor-directory {
  min-height: 100vh;
  background: #f8f9fa;
}

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4rem 0 3rem;
  margin-bottom: 2rem;
}

.page-title {
  font-size: 3rem;
  font-weight: 700;
  margin-bottom: 1rem;
  color: #ffffff !important;
}

.page-subtitle {
  font-size: 1.2rem;
  opacity: 1;
  margin: 0;
  color: #ffffff !important;
}

.header-stats {
  display: flex;
  gap: 2rem;
  justify-content: flex-end;
}

.stat-item {
  text-align: center;
}

.stat-number {
  display: block;
  font-size: 2rem;
  font-weight: 700;
  color: #ffffff !important;
}

.stat-label {
  font-size: 0.9rem;
  opacity: 1;
  color: #ffffff !important;
}

.filters-section {
  margin-bottom: 2rem;
}

.filters-card {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.search-box {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  color: #333333;
  z-index: 2;
}

.search-input {
  padding-left: 3rem;
  padding-right: 3rem;
  border-radius: 25px;
  border: 2px solid #e9ecef;
  transition: all 0.3s ease;
}

.search-input:focus {
  border-color: #007bff;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}

.clear-search {
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #333333;
  cursor: pointer;
}

.view-toggle {
  display: flex;
  border-radius: 6px;
  overflow: hidden;
}

.view-toggle .btn {
  border-radius: 0;
  border-right: none;
}

.view-toggle .btn:last-child {
  border-right: 1px solid #dee2e6;
}

.view-toggle .btn.active {
  background-color: #007bff;
  border-color: #007bff;
  color: white;
}

.sidebar {
  position: sticky;
  top: 2rem;
}

.sidebar-section {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.sidebar-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: #2c3e50;
}

.featured-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.featured-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.featured-item:hover {
  background: #f8f9fa;
}

.featured-logo {
  flex-shrink: 0;
}

.featured-logo .logo-image {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  object-fit: cover;
}

.featured-logo .logo-placeholder {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  background: #e9ecef;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.featured-name {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0;
  color: #2c3e50;
}

.featured-booth {
  font-size: 0.8rem;
  color: #333333;
  margin: 0;
}

.tags-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag-filter-btn {
  padding: 0.25rem 0.75rem;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 15px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.tag-filter-btn:hover {
  background: #e9ecef;
}

.tag-filter-btn.active {
  background: #007bff;
  border-color: #007bff;
  color: white;
}

.quick-stats {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-size: 0.9rem;
  color: #000000;
}

.stat-value {
  font-weight: 600;
  color: #2c3e50;
}

.loading-state,
.error-state,
.empty-state {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.exhibitor-grid {
  margin-bottom: 2rem;
}

.exhibitor-list-view {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  margin-bottom: 2rem;
}

.exhibitor-list-item {
  border-bottom: 1px solid #e9ecef;
  cursor: pointer;
  transition: all 0.3s ease;
}

.exhibitor-list-item:hover {
  background: #f8f9fa;
}

.exhibitor-list-item:last-child {
  border-bottom: none;
}

.list-item-content {
  display: flex;
  align-items: center;
  padding: 1.5rem;
  gap: 1.5rem;
}

.list-item-logo {
  flex-shrink: 0;
}

.list-item-logo .logo-image {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  object-fit: cover;
}

.list-item-logo .logo-placeholder {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  background: #e9ecef;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6c757d;
  font-size: 1.5rem;
}

.list-item-info {
  flex: 1;
  min-width: 0;
}

.list-item-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.exhibitor-name {
  font-size: 1.2rem;
  font-weight: 600;
  margin: 0;
  color: #2c3e50;
}

.exhibitor-badges {
  display: flex;
  gap: 0.5rem;
}

.badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-featured {
  background: #fff3cd;
  color: #856404;
}

.badge-booth {
  background: #d1ecf1;
  color: #0c5460;
}

.exhibitor-tagline {
  font-style: italic;
  color: #333333;
  margin: 0 0 0.5rem 0;
}

.exhibitor-description {
  color: #000000;
  margin: 0;
  line-height: 1.5;
}

.list-item-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex-shrink: 0;
}

.pagination-nav {
  margin: 2rem 0;
}

.pagination .page-link {
  border-radius: 6px;
  margin: 0 0.25rem;
  border: 1px solid #dee2e6;
}

.pagination .page-item.active .page-link {
  background-color: #007bff;
  border-color: #007bff;
}

@media (max-width: 992px) {
  .page-title {
    font-size: 2rem;
  }
  
  .header-stats {
    justify-content: center;
    margin-top: 2rem;
  }
  
  .sidebar {
    position: static;
    margin-bottom: 2rem;
  }
  
  .list-item-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }
  
  .list-item-actions {
    flex-direction: row;
    width: 100%;
  }
}

@media (max-width: 768px) {
  .filters-card .row > div {
    margin-bottom: 1rem;
  }
  
  .view-toggle {
    width: 100%;
  }
  
  .results-count {
    text-align: center;
  }
}
</style>