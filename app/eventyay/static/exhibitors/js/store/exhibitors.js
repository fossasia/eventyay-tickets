import { defineStore } from 'pinia'
import axios from 'axios'

// Configure axios defaults
axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'

export const useExhibitorStore = defineStore('exhibitors', {
  state: () => ({
    // Exhibitor data
    exhibitors: [],
    currentExhibitor: null,
    featuredExhibitors: [],
    
    // Pagination and filtering
    pagination: {
      currentPage: 1,
      totalPages: 1,
      totalCount: 0,
      pageSize: 12
    },
    
    filters: {
      search: '',
      featured: false,
      tags: [],
      sortBy: 'sort_order'
    },
    
    // Loading states
    loading: {
      exhibitors: false,
      currentExhibitor: false,
      contact: false,
      analytics: false
    },
    
    // Error handling
    errors: {
      exhibitors: null,
      currentExhibitor: null,
      contact: null,
      analytics: null
    },
    
    // Analytics data
    analytics: {},
    
    // Contact requests
    contactRequests: [],
    
    // Leads
    leads: [],
    
    // Notifications
    notifications: [],
    
    // Cache
    cache: {
      exhibitors: new Map(),
      lastFetch: null,
      ttl: 5 * 60 * 1000 // 5 minutes
    }
  }),
  
  getters: {
    // Get exhibitors with applied filters
    filteredExhibitors: (state) => {
      let filtered = [...state.exhibitors]
      
      // Apply search filter
      if (state.filters.search) {
        const query = state.filters.search.toLowerCase()
        filtered = filtered.filter(exhibitor => 
          exhibitor.name.toLowerCase().includes(query) ||
          exhibitor.tagline?.toLowerCase().includes(query) ||
          exhibitor.booth_name?.toLowerCase().includes(query)
        )
      }
      
      // Apply featured filter
      if (state.filters.featured) {
        filtered = filtered.filter(exhibitor => exhibitor.featured)
      }
      
      // Apply tag filters
      if (state.filters.tags.length > 0) {
        filtered = filtered.filter(exhibitor => 
          exhibitor.tags?.some(tag => state.filters.tags.includes(tag.name))
        )
      }
      
      // Apply sorting
      switch (state.filters.sortBy) {
        case 'name':
          filtered.sort((a, b) => a.name.localeCompare(b.name))
          break
        case 'featured':
          filtered.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
          break
        case 'created_at':
          filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
          break
        default:
          filtered.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))
      }
      
      return filtered
    },
    
    // Get exhibitor by booth ID
    getExhibitorByBoothId: (state) => (boothId) => {
      return state.exhibitors.find(exhibitor => exhibitor.booth_id === boothId)
    },
    
    // Get exhibitor by ID
    getExhibitorById: (state) => (id) => {
      return state.exhibitors.find(exhibitor => exhibitor.id === id)
    },
    
    // Check if cache is valid
    isCacheValid: (state) => {
      if (!state.cache.lastFetch) return false
      return Date.now() - state.cache.lastFetch < state.cache.ttl
    },
    
    // Get unique tags from all exhibitors
    availableTags: (state) => {
      const tags = new Set()
      state.exhibitors.forEach(exhibitor => {
        exhibitor.tags?.forEach(tag => tags.add(tag.name))
      })
      return Array.from(tags).sort()
    },
    
    // Get loading state for specific operation
    isLoading: (state) => (operation) => {
      return state.loading[operation] || false
    },
    
    // Get error for specific operation
    getError: (state) => (operation) => {
      return state.errors[operation]
    }
  },
  
  actions: {
    // Fetch exhibitors list
    async fetchExhibitors(params = {}) {
      // Check cache first
      if (this.isCacheValid && !params.force) {
        return this.exhibitors
      }
      
      this.loading.exhibitors = true
      this.errors.exhibitors = null
      
      try {
        const response = await axios.get('/api/v1/exhibitors/', {
          params: {
            page: this.pagination.currentPage,
            page_size: this.pagination.pageSize,
            search: this.filters.search,
            featured: this.filters.featured || undefined,
            ordering: this.filters.sortBy,
            ...params
          }
        })
        
        this.exhibitors = response.data.results || response.data
        
        // Update pagination if available
        if (response.data.count !== undefined) {
          this.pagination.totalCount = response.data.count
          this.pagination.totalPages = Math.ceil(response.data.count / this.pagination.pageSize)
        }
        
        // Update cache
        this.cache.lastFetch = Date.now()
        
        return this.exhibitors
      } catch (error) {
        this.errors.exhibitors = this.handleError(error)
        throw error
      } finally {
        this.loading.exhibitors = false
      }
    },
    
    // Fetch single exhibitor by ID
    async fetchExhibitor(id) {
      // Check cache first
      const cached = this.cache.exhibitors.get(id)
      if (cached && Date.now() - cached.timestamp < this.cache.ttl) {
        this.currentExhibitor = cached.data
        return cached.data
      }
      
      this.loading.currentExhibitor = true
      this.errors.currentExhibitor = null
      
      try {
        const response = await axios.get(`/api/v1/exhibitors/${id}/`)
        this.currentExhibitor = response.data
        
        // Cache the result
        this.cache.exhibitors.set(id, {
          data: response.data,
          timestamp: Date.now()
        })
        
        return response.data
      } catch (error) {
        this.errors.currentExhibitor = this.handleError(error)
        throw error
      } finally {
        this.loading.currentExhibitor = false
      }
    },
    
    // Fetch exhibitor by booth ID
    async fetchExhibitorByBoothId(boothId) {
      // First check if we already have it in the list
      const existing = this.getExhibitorByBoothId(boothId)
      if (existing) {
        return this.fetchExhibitor(existing.id)
      }
      
      this.loading.currentExhibitor = true
      this.errors.currentExhibitor = null
      
      try {
        const response = await axios.get('/api/v1/exhibitors/', {
          params: { booth_id: boothId }
        })
        
        const exhibitors = response.data.results || response.data
        if (exhibitors.length > 0) {
          return this.fetchExhibitor(exhibitors[0].id)
        } else {
          throw new Error('Exhibitor not found')
        }
      } catch (error) {
        this.errors.currentExhibitor = this.handleError(error)
        throw error
      } finally {
        this.loading.currentExhibitor = false
      }
    },
    
    // Fetch featured exhibitors
    async fetchFeaturedExhibitors(limit = 6) {
      try {
        const response = await axios.get('/api/v1/exhibitors/featured/', {
          params: { limit }
        })
        
        this.featuredExhibitors = response.data.results || response.data
        return this.featuredExhibitors
      } catch (error) {
        console.error('Failed to fetch featured exhibitors:', error)
        return []
      }
    },
    
    // Submit contact request
    async submitContactRequest(exhibitorId, contactData) {
      this.loading.contact = true
      this.errors.contact = null
      
      try {
        const response = await axios.post(`/api/v1/exhibitors/${exhibitorId}/contact/`, contactData)
        
        // Add to contact requests list
        this.contactRequests.unshift(response.data)
        
        this.showNotification({
          type: 'success',
          message: 'Your message has been sent successfully!'
        })
        
        return response.data
      } catch (error) {
        this.errors.contact = this.handleError(error)
        throw error
      } finally {
        this.loading.contact = false
      }
    },
    
    // Fetch analytics for exhibitor
    async fetchAnalytics(exhibitorId) {
      this.loading.analytics = true
      this.errors.analytics = null
      
      try {
        const response = await axios.get(`/api/v1/exhibitors/${exhibitorId}/analytics/`)
        this.analytics[exhibitorId] = response.data
        return response.data
      } catch (error) {
        this.errors.analytics = this.handleError(error)
        throw error
      } finally {
        this.loading.analytics = false
      }
    },
    
    // Fetch leads for exhibitor
    async fetchLeads(exhibitorId) {
      try {
        const response = await axios.get(`/api/v1/exhibitors/${exhibitorId}/leads/`)
        this.leads = response.data
        return response.data
      } catch (error) {
        console.error('Failed to fetch leads:', error)
        throw error
      }
    },
    
    // Fetch contact requests for exhibitor
    async fetchContactRequests(exhibitorId) {
      try {
        const response = await axios.get(`/api/v1/exhibitors/${exhibitorId}/contact_requests/`)
        this.contactRequests = response.data
        return response.data
      } catch (error) {
        console.error('Failed to fetch contact requests:', error)
        throw error
      }
    },
    
    // Search exhibitors
    async searchExhibitors(query, options = {}) {
      try {
        const response = await axios.get('/api/v1/exhibitors/search/', {
          params: {
            q: query,
            ...options
          }
        })
        
        return response.data.exhibitors || response.data
      } catch (error) {
        console.error('Search failed:', error)
        return []
      }
    },
    
    // Update filters
    updateFilters(newFilters) {
      this.filters = { ...this.filters, ...newFilters }
      this.pagination.currentPage = 1 // Reset to first page
    },
    
    // Update pagination
    updatePagination(newPagination) {
      this.pagination = { ...this.pagination, ...newPagination }
    },
    
    // Clear current exhibitor
    clearCurrentExhibitor() {
      this.currentExhibitor = null
      this.errors.currentExhibitor = null
    },
    
    // Clear cache
    clearCache() {
      this.cache.exhibitors.clear()
      this.cache.lastFetch = null
    },
    
    // Show notification
    showNotification(notification) {
      const id = Date.now().toString()
      this.notifications.push({
        id,
        ...notification,
        timestamp: Date.now()
      })
      
      // Auto-remove after 5 seconds
      setTimeout(() => {
        this.removeNotification(id)
      }, 5000)
    },
    
    // Remove notification
    removeNotification(id) {
      const index = this.notifications.findIndex(n => n.id === id)
      if (index > -1) {
        this.notifications.splice(index, 1)
      }
    },
    
    // Clear all notifications
    clearNotifications() {
      this.notifications = []
    },
    
    // Handle API errors
    handleError(error) {
      if (error.response) {
        // Server responded with error status
        const status = error.response.status
        const data = error.response.data
        
        if (status === 404) {
          return 'Exhibitor not found'
        } else if (status === 403) {
          return 'Access denied'
        } else if (status === 500) {
          return 'Server error. Please try again later.'
        } else if (data.detail) {
          return data.detail
        } else if (data.message) {
          return data.message
        } else {
          return `Error ${status}: ${error.response.statusText}`
        }
      } else if (error.request) {
        // Network error
        return 'Network error. Please check your connection.'
      } else {
        // Other error
        return error.message || 'An unexpected error occurred'
      }
    },
    
    // Reset store state
    resetStore() {
      this.exhibitors = []
      this.currentExhibitor = null
      this.featuredExhibitors = []
      this.pagination = {
        currentPage: 1,
        totalPages: 1,
        totalCount: 0,
        pageSize: 12
      }
      this.filters = {
        search: '',
        featured: false,
        tags: [],
        sortBy: 'sort_order'
      }
      this.loading = {
        exhibitors: false,
        currentExhibitor: false,
        contact: false,
        analytics: false
      }
      this.errors = {
        exhibitors: null,
        currentExhibitor: null,
        contact: null,
        analytics: null
      }
      this.analytics = {}
      this.contactRequests = []
      this.leads = []
      this.notifications = []
      this.clearCache()
    }
  }
})