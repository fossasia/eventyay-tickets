<template>
  <div class="exhibitor-directory">
    <!-- Header Section -->
    <div class="directory-header">
      <div class="d-flex justify-content-between align-items-center mb-4">
        <h1 class="page-title">{{ $t('exhibitors.directory.title') }}</h1>
        <div class="header-actions">
          <button 
            v-if="canManageExhibitors"
            @click="showCreateModal = true"
            class="btn btn-primary"
          >
            <i class="fa fa-plus"></i>
            {{ $t('exhibitors.actions.add') }}
          </button>
        </div>
      </div>
      
      <!-- Search and Filters -->
      <div class="directory-controls mb-4">
        <div class="row">
          <div class="col-md-6">
            <div class="search-box">
              <div class="input-group">
                <input
                  v-model="searchQuery"
                  type="text"
                  class="form-control"
                  :placeholder="$t('exhibitors.search.placeholder')"
                  @input="handleSearch"
                >
                <div class="input-group-append">
                  <span class="input-group-text">
                    <i class="fa fa-search"></i>
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div class="col-md-3">
            <select 
              v-model="selectedCategory" 
              class="form-control"
              @change="handleCategoryFilter"
            >
              <option value="">{{ $t('exhibitors.filter.all_categories') }}</option>
              <option 
                v-for="category in categories" 
                :key="category" 
                :value="category"
              >
                {{ category }}
              </option>
            </select>
          </div>
          <div class="col-md-3">
            <div class="view-toggle">
              <div class="btn-group" role="group">
                <button
                  type="button"
                  class="btn btn-outline-secondary"
                  :class="{ active: viewMode === 'grid' }"
                  @click="viewMode = 'grid'"
                >
                  <i class="fa fa-th"></i>
                </button>
                <button
                  type="button"
                  class="btn btn-outline-secondary"
                  :class="{ active: viewMode === 'list' }"
                  @click="viewMode = 'list'"
                >
                  <i class="fa fa-list"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border" role="status">
        <span class="sr-only">{{ $t('common.loading') }}</span>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredExhibitors.length === 0 && !searchQuery" class="empty-state text-center py-5">
      <div class="empty-icon mb-3">
        <i class="fa fa-building fa-3x text-muted"></i>
      </div>
      <h3 class="text-muted">{{ $t('exhibitors.empty.title') }}</h3>
      <p class="text-muted mb-4">{{ $t('exhibitors.empty.description') }}</p>
      <button 
        v-if="canManageExhibitors"
        @click="showCreateModal = true"
        class="btn btn-primary btn-lg"
      >
        <i class="fa fa-plus"></i>
        {{ $t('exhibitors.actions.add_first') }}
      </button>
    </div>

    <!-- No Results State -->
    <div v-else-if="filteredExhibitors.length === 0" class="no-results text-center py-5">
      <div class="empty-icon mb-3">
        <i class="fa fa-search fa-3x text-muted"></i>
      </div>
      <h3 class="text-muted">{{ $t('exhibitors.search.no_results') }}</h3>
      <p class="text-muted">{{ $t('exhibitors.search.try_different') }}</p>
      <button @click="clearSearch" class="btn btn-outline-primary">
        {{ $t('exhibitors.search.clear') }}
      </button>
    </div>

    <!-- Exhibitor Grid View -->
    <div v-else-if="viewMode === 'grid'" class="exhibitor-grid">
      <div class="row">
        <div 
          v-for="exhibitor in paginatedExhibitors" 
          :key="exhibitor.id"
          class="col-lg-4 col-md-6 mb-4"
        >
          <ExhibitorCard
            :exhibitor="exhibitor"
            :can-manage="canManageExhibitors"
            @view="viewExhibitor"
            @edit="editExhibitor"
            @delete="deleteExhibitor"
            @copy-key="copyExhibitorKey"
          />
        </div>
      </div>
    </div>

    <!-- Exhibitor List View -->
    <div v-else class="exhibitor-list">
      <div class="table-responsive">
        <table class="table table-hover">
          <thead>
            <tr>
              <th>{{ $t('exhibitors.fields.name') }}</th>
              <th>{{ $t('exhibitors.fields.booth') }}</th>
              <th>{{ $t('exhibitors.fields.leads') }}</th>
              <th>{{ $t('exhibitors.fields.status') }}</th>
              <th v-if="canManageExhibitors" class="text-right">{{ $t('common.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="exhibitor in paginatedExhibitors" 
              :key="exhibitor.id"
              class="exhibitor-row"
              @click="viewExhibitor(exhibitor)"
            >
              <td>
                <div class="exhibitor-info">
                  <img 
                    v-if="exhibitor.logo_url"
                    :src="exhibitor.logo_url"
                    :alt="exhibitor.name"
                    class="exhibitor-logo-sm"
                  >
                  <div>
                    <strong>{{ exhibitor.name }}</strong>
                    <div v-if="exhibitor.description" class="text-muted small">
                      {{ truncateText(exhibitor.description, 100) }}
                    </div>
                  </div>
                </div>
              </td>
              <td>
                <span class="badge badge-secondary">{{ exhibitor.booth_name }}</span>
              </td>
              <td>
                <span class="badge badge-info">{{ exhibitor.lead_count || 0 }}</span>
              </td>
              <td>
                <span 
                  class="badge"
                  :class="exhibitor.is_active ? 'badge-success' : 'badge-secondary'"
                >
                  {{ exhibitor.is_active ? $t('common.active') : $t('common.inactive') }}
                </span>
              </td>
              <td v-if="canManageExhibitors" class="text-right" @click.stop>
                <div class="btn-group btn-group-sm">
                  <button
                    @click="editExhibitor(exhibitor)"
                    class="btn btn-outline-primary"
                    :title="$t('common.edit')"
                  >
                    <i class="fa fa-edit"></i>
                  </button>
                  <button
                    @click="copyExhibitorKey(exhibitor)"
                    class="btn btn-outline-secondary"
                    :title="$t('exhibitors.actions.copy_key')"
                  >
                    <i class="fa fa-key"></i>
                  </button>
                  <button
                    @click="deleteExhibitor(exhibitor)"
                    class="btn btn-outline-danger"
                    :title="$t('common.delete')"
                  >
                    <i class="fa fa-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <nav v-if="totalPages > 1" class="mt-4">
      <ul class="pagination justify-content-center">
        <li class="page-item" :class="{ disabled: currentPage === 1 }">
          <button 
            class="page-link" 
            @click="changePage(currentPage - 1)"
            :disabled="currentPage === 1"
          >
            {{ $t('pagination.previous') }}
          </button>
        </li>
        <li 
          v-for="page in visiblePages" 
          :key="page"
          class="page-item"
          :class="{ active: page === currentPage }"
        >
          <button class="page-link" @click="changePage(page)">
            {{ page }}
          </button>
        </li>
        <li class="page-item" :class="{ disabled: currentPage === totalPages }">
          <button 
            class="page-link" 
            @click="changePage(currentPage + 1)"
            :disabled="currentPage === totalPages"
          >
            {{ $t('pagination.next') }}
          </button>
        </li>
      </ul>
    </nav>

    <!-- Create/Edit Modal -->
    <ExhibitorModal
      v-if="showCreateModal || showEditModal"
      :exhibitor="selectedExhibitor"
      :is-edit="showEditModal"
      @save="handleSaveExhibitor"
      @cancel="closeModals"
    />

    <!-- Delete Confirmation Modal -->
    <ConfirmModal
      v-if="showDeleteModal"
      :title="$t('exhibitors.delete.title')"
      :message="$t('exhibitors.delete.message', { name: selectedExhibitor?.name })"
      @confirm="confirmDelete"
      @cancel="showDeleteModal = false"
    />
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExhibitorStore } from '../stores/exhibitorStore'
import { useNotificationStore } from '../stores/notificationStore'
import ExhibitorCard from './ExhibitorCard.vue'
import ExhibitorModal from './ExhibitorModal.vue'
import ConfirmModal from './ConfirmModal.vue'

export default {
  name: 'ExhibitorDirectory',
  components: {
    ExhibitorCard,
    ExhibitorModal,
    ConfirmModal
  },
  props: {
    canManageExhibitors: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const { t } = useI18n()
    const exhibitorStore = useExhibitorStore()
    const notificationStore = useNotificationStore()

    // Reactive data
    const searchQuery = ref('')
    const selectedCategory = ref('')
    const viewMode = ref('grid')
    const currentPage = ref(1)
    const itemsPerPage = 12
    const showCreateModal = ref(false)
    const showEditModal = ref(false)
    const showDeleteModal = ref(false)
    const selectedExhibitor = ref(null)

    // Computed properties
    const loading = computed(() => exhibitorStore.loading)
    const exhibitors = computed(() => exhibitorStore.exhibitors)

    const categories = computed(() => {
      const cats = new Set()
      exhibitors.value.forEach(exhibitor => {
        if (exhibitor.categories) {
          exhibitor.categories.forEach(cat => cats.add(cat))
        }
      })
      return Array.from(cats).sort()
    })

    const filteredExhibitors = computed(() => {
      let filtered = exhibitors.value.filter(exhibitor => exhibitor.is_active)

      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        filtered = filtered.filter(exhibitor =>
          exhibitor.name.toLowerCase().includes(query) ||
          (exhibitor.description && exhibitor.description.toLowerCase().includes(query)) ||
          exhibitor.booth_name.toLowerCase().includes(query)
        )
      }

      if (selectedCategory.value) {
        filtered = filtered.filter(exhibitor =>
          exhibitor.categories && exhibitor.categories.includes(selectedCategory.value)
        )
      }

      return filtered.sort((a, b) => {
        if (a.featured && !b.featured) return -1
        if (!a.featured && b.featured) return 1
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order
        return a.name.localeCompare(b.name)
      })
    })

    const totalPages = computed(() =>
      Math.ceil(filteredExhibitors.value.length / itemsPerPage)
    )

    const paginatedExhibitors = computed(() => {
      const start = (currentPage.value - 1) * itemsPerPage
      const end = start + itemsPerPage
      return filteredExhibitors.value.slice(start, end)
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
          pages.push('...')
          pages.push(total)
        } else if (current >= total - 3) {
          pages.push(1)
          pages.push('...')
          for (let i = total - 4; i <= total; i++) pages.push(i)
        } else {
          pages.push(1)
          pages.push('...')
          for (let i = current - 1; i <= current + 1; i++) pages.push(i)
          pages.push('...')
          pages.push(total)
        }
      }
      
      return pages
    })

    // Methods
    const handleSearch = () => {
      currentPage.value = 1
    }

    const handleCategoryFilter = () => {
      currentPage.value = 1
    }

    const clearSearch = () => {
      searchQuery.value = ''
      selectedCategory.value = ''
      currentPage.value = 1
    }

    const changePage = (page) => {
      if (page >= 1 && page <= totalPages.value) {
        currentPage.value = page
      }
    }

    const viewExhibitor = (exhibitor) => {
      // Navigate to exhibitor detail page
      window.location.href = `/control/exhibitors/${exhibitor.id}/`
    }

    const editExhibitor = (exhibitor) => {
      selectedExhibitor.value = exhibitor
      showEditModal.value = true
    }

    const deleteExhibitor = (exhibitor) => {
      selectedExhibitor.value = exhibitor
      showDeleteModal.value = true
    }

    const copyExhibitorKey = async (exhibitor) => {
      try {
        await navigator.clipboard.writeText(exhibitor.key)
        notificationStore.addSuccess(t('exhibitors.actions.key_copied'))
      } catch (error) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea')
        textArea.value = exhibitor.key
        document.body.appendChild(textArea)
        textArea.select()
        document.execCommand('copy')
        document.body.removeChild(textArea)
        notificationStore.addSuccess(t('exhibitors.actions.key_copied'))
      }
    }

    const handleSaveExhibitor = async (exhibitorData) => {
      try {
        if (showEditModal.value) {
          await exhibitorStore.updateExhibitor(selectedExhibitor.value.id, exhibitorData)
          notificationStore.addSuccess(t('exhibitors.messages.updated'))
        } else {
          await exhibitorStore.createExhibitor(exhibitorData)
          notificationStore.addSuccess(t('exhibitors.messages.created'))
        }
        closeModals()
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.save_error'))
      }
    }

    const confirmDelete = async () => {
      try {
        await exhibitorStore.deleteExhibitor(selectedExhibitor.value.id)
        notificationStore.addSuccess(t('exhibitors.messages.deleted'))
        showDeleteModal.value = false
        selectedExhibitor.value = null
      } catch (error) {
        notificationStore.addError(t('exhibitors.messages.delete_error'))
      }
    }

    const closeModals = () => {
      showCreateModal.value = false
      showEditModal.value = false
      selectedExhibitor.value = null
    }

    const truncateText = (text, maxLength) => {
      if (!text) return ''
      return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
    }

    // Watch for search changes to reset pagination
    watch([searchQuery, selectedCategory], () => {
      currentPage.value = 1
    })

    // Lifecycle
    onMounted(() => {
      exhibitorStore.fetchExhibitors()
    })

    return {
      // Reactive data
      searchQuery,
      selectedCategory,
      viewMode,
      currentPage,
      showCreateModal,
      showEditModal,
      showDeleteModal,
      selectedExhibitor,
      
      // Computed
      loading,
      exhibitors,
      categories,
      filteredExhibitors,
      totalPages,
      paginatedExhibitors,
      visiblePages,
      
      // Methods
      handleSearch,
      handleCategoryFilter,
      clearSearch,
      changePage,
      viewExhibitor,
      editExhibitor,
      deleteExhibitor,
      copyExhibitorKey,
      handleSaveExhibitor,
      confirmDelete,
      closeModals,
      truncateText
    }
  }
}
</script>

<style scoped>
.exhibitor-directory {
  padding: 20px;
}

.page-title {
  color: #333;
  margin-bottom: 0;
}

.directory-controls {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

.search-box .input-group-text {
  background: white;
  border-left: none;
}

.search-box .form-control {
  border-right: none;
}

.view-toggle .btn {
  border-color: #dee2e6;
}

.view-toggle .btn.active {
  background-color: #007bff;
  border-color: #007bff;
  color: white;
}

.exhibitor-grid {
  margin-top: 20px;
}

.exhibitor-list {
  margin-top: 20px;
}

.exhibitor-row {
  cursor: pointer;
  transition: background-color 0.2s;
}

.exhibitor-row:hover {
  background-color: #f8f9fa;
}

.exhibitor-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.exhibitor-logo-sm {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 4px;
}

.empty-state,
.no-results {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.empty-icon {
  opacity: 0.5;
}

.pagination .page-link {
  color: #007bff;
  border-color: #dee2e6;
}

.pagination .page-item.active .page-link {
  background-color: #007bff;
  border-color: #007bff;
}

.pagination .page-item.disabled .page-link {
  color: #6c757d;
  background-color: #fff;
  border-color: #dee2e6;
}

@media (max-width: 768px) {
  .directory-controls .row > div {
    margin-bottom: 15px;
  }
  
  .directory-controls .row > div:last-child {
    margin-bottom: 0;
  }
  
  .header-actions {
    margin-top: 15px;
  }
  
  .d-flex.justify-content-between {
    flex-direction: column;
    align-items: flex-start !important;
  }
}
</style>