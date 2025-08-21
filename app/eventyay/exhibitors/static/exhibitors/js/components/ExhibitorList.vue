<template>
  <div class="exhibitor-list">
    <!-- Search and Filters -->
    <div class="exhibitor-filters mb-4">
      <div class="row">
        <div class="col-md-6">
          <div class="search-box">
            <input
              v-model="searchQuery"
              type="text"
              class="form-control"
              :placeholder="$t('Search exhibitors...')"
              @input="debouncedSearch"
            />
            <i class="fas fa-search search-icon"></i>
          </div>
        </div>
        <div class="col-md-3">
          <select v-model="sortBy" class="form-control" @change="applyFilters">
            <option value="sort_order">{{ $t('Default Order') }}</option>
            <option value="name">{{ $t('Name A-Z') }}</option>
            <option value="featured">{{ $t('Featured First') }}</option>
            <option value="created_at">{{ $t('Newest First') }}</option>
          </select>
        </div>
        <div class="col-md-3">
          <div class="form-check">
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
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="text-center py-4">
      <div class="spinner-border" role="status">
        <span class="sr-only">{{ $t('Loading...') }}</span>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="alert alert-danger" role="alert">
      <i class="fas fa-exclamation-triangle me-2"></i>
      {{ error }}
      <button class="btn btn-sm btn-outline-danger ms-2" @click="fetchExhibitors">
        {{ $t('Retry') }}
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredExhibitors.length === 0" class="empty-state text-center py-5">
      <i class="fas fa-store fa-3x text-muted mb-3"></i>
      <h4 class="text-muted">{{ $t('No exhibitors found') }}</h4>
      <p class="text-muted">
        {{ searchQuery ? $t('Try adjusting your search criteria') : $t('No exhibitors are currently available') }}
      </p>
      <button v-if="searchQuery" class="btn btn-primary" @click="clearSearch">
        {{ $t('Clear Search') }}
      </button>
    </div>

    <!-- Exhibitor Grid -->
    <div v-else class="exhibitor-grid">
      <div class="row">
        <div
          v-for="exhibitor in paginatedExhibitors"
          :key="exhibitor.id"
          class="col-lg-4 col-md-6 col-sm-12 mb-4"
        >
          <ExhibitorCard
            :exhibitor="exhibitor"
            @click="viewExhibitor(exhibitor)"
            @contact="openContactModal(exhibitor)"
          />
        </div>
      </div>

      <!-- Pagination -->
      <nav v-if="totalPages > 1" aria-label="Exhibitor pagination">
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
    </div>

    <!-- Results Info -->
    <div v-if="!loading && !error" class="results-info text-center mt-3">
      <small class="text-muted">
        {{ $t('Showing {start} to {end} of {total} exhibitors', {
          start: (currentPage - 1) * itemsPerPage + 1,
          end: Math.min(currentPage * itemsPerPage, filteredExhibitors.length),
          total: filteredExhibitors.length
        }) }}
      </small>
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
import ExhibitorCard from './ExhibitorCard.vue'
import ContactModal from './ContactModal.vue'

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
  },
  featured: {
    type: Boolean,
    default: false
  },
  limit: {
    type: Number,
    default: null
  }
})

// Composables
const router = useRouter()
const exhibitorStore = useExhibitorStore()

// Reactive data
const searchQuery = ref('')
const sortBy = ref('sort_order')
const featuredOnly = ref(props.featured)
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
      exhibitor.booth_name?.toLowerCase().includes(query)
    )
  }
  
  // Apply featured filter
  if (featuredOnly.value) {
    exhibitors = exhibitors.filter(exhibitor => exhibitor.featured)
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
  
  // Apply limit if specified
  if (props.limit) {
    exhibitors = exhibitors.slice(0, props.limit)
  }
  
  return exhibitors
})

const paginatedExhibitors = computed(() => {
  if (props.limit) {
    return filteredExhibitors.value
  }
  
  const start = (currentPage.value - 1) * itemsPerPage.value
  const end = start + itemsPerPage.value
  return filteredExhibitors.value.slice(start, end)
})

const totalPages = computed(() => {
  if (props.limit) return 1
  return Math.ceil(filteredExhibitors.value.length / itemsPerPage.value)
})

const visiblePages = computed(() => {
  const pages = []
  const total = totalPages.value
  const current = currentPage.value
  
  // Show up to 5 pages around current page
  let start = Math.max(1, current - 2)
  let end = Math.min(total, current + 2)
  
  // Adjust if we're near the beginning or end
  if (end - start < 4) {
    if (start === 1) {
      end = Math.min(total, start + 4)
    } else {
      start = Math.max(1, end - 4)
    }
  }
  
  for (let i = start; i <= end; i++) {
    pages.push(i)
  }
  
  return pages
})

// Methods
const fetchExhibitors = async () => {
  loading.value = true
  error.value = null
  
  try {
    await exhibitorStore.fetchExhibitors({
      event_id: props.eventId,
      featured: props.featured
    })
  } catch (err) {
    error.value = err.message || 'Failed to load exhibitors'
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  currentPage.value = 1
}

const debouncedSearch = debounce(() => {
  applyFilters()
}, 300)

const clearSearch = () => {
  searchQuery.value = ''
  applyFilters()
}

const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    // Scroll to top of list
    document.querySelector('.exhibitor-list')?.scrollIntoView({ behavior: 'smooth' })
  }
}

const viewExhibitor = (exhibitor) => {
  router.push({
    name: 'exhibitor-detail',
    params: { boothId: exhibitor.booth_id }
  })
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
  // Show success message
  exhibitorStore.showNotification({
    type: 'success',
    message: 'Your message has been sent successfully!'
  })
}

// Watchers
watch(() => props.eventId, () => {
  if (props.eventId) {
    fetchExhibitors()
  }
})

watch(() => props.featured, (newVal) => {
  featuredOnly.value = newVal
  applyFilters()
})

// Lifecycle
onMounted(() => {
  fetchExhibitors()
})
</script>

<style scoped>
.exhibitor-list {
  padding: 1rem 0;
}

.search-box {
  position: relative;
}

.search-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #6c757d;
  pointer-events: none;
}

.exhibitor-grid {
  min-height: 400px;
}

.empty-state {
  padding: 3rem 1rem;
}

.empty-state i {
  opacity: 0.5;
}

.pagination {
  margin-top: 2rem;
}

.page-link {
  border: none;
  color: #6c757d;
  padding: 0.5rem 0.75rem;
}

.page-link:hover {
  background-color: #f8f9fa;
  color: #495057;
}

.page-item.active .page-link {
  background-color: #007bff;
  border-color: #007bff;
  color: white;
}

.results-info {
  margin-top: 1rem;
  padding: 0.5rem;
}

@media (max-width: 768px) {
  .exhibitor-filters .row > div {
    margin-bottom: 0.5rem;
  }
  
  .search-box {
    margin-bottom: 1rem;
  }
}
</style>