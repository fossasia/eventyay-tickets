import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { exhibitorApi } from '../api/exhibitor'

export const useExhibitorStore = defineStore('exhibitor', () => {
  // State
  const exhibitors = ref([])
  const currentExhibitor = ref(null)
  const leadStats = ref(null)
  const recentLeads = ref([])
  const loading = ref(false)
  const error = ref(null)
  const pagination = ref({
    page: 1,
    pageSize: 20,
    total: 0,
    totalPages: 0
  })

  // Getters
  const activeExhibitors = computed(() => 
    exhibitors.value.filter(exhibitor => exhibitor.is_active)
  )

  const featuredExhibitors = computed(() => 
    activeExhibitors.value.filter(exhibitor => exhibitor.featured)
  )

  const exhibitorById = computed(() => (id) => 
    exhibitors.value.find(exhibitor => exhibitor.id === id)
  )

  const totalLeads = computed(() => 
    exhibitors.value.reduce((total, exhibitor) => total + (exhibitor.lead_count || 0), 0)
  )

  // Actions
  const fetchExhibitors = async (params = {}) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.getExhibitors(params)
      
      if (response.success) {
        exhibitors.value = response.exhibitors || []
        
        // Update pagination if provided
        if (response.pagination) {
          pagination.value = { ...pagination.value, ...response.pagination }
        }
      } else {
        throw new Error(response.error || 'Failed to fetch exhibitors')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error fetching exhibitors:', err)
    } finally {
      loading.value = false
    }
  }

  const fetchExhibitor = async (id) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.getExhibitor(id)
      
      if (response.success) {
        currentExhibitor.value = response.exhibitor
        
        // Update the exhibitor in the list if it exists
        const index = exhibitors.value.findIndex(e => e.id === id)
        if (index !== -1) {
          exhibitors.value[index] = response.exhibitor
        }
      } else {
        throw new Error(response.error || 'Failed to fetch exhibitor')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error fetching exhibitor:', err)
    } finally {
      loading.value = false
    }
  }

  const createExhibitor = async (exhibitorData) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.createExhibitor(exhibitorData)
      
      if (response.success) {
        const newExhibitor = response.exhibitor
        exhibitors.value.push(newExhibitor)
        return newExhibitor
      } else {
        throw new Error(response.error || 'Failed to create exhibitor')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error creating exhibitor:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const updateExhibitor = async (id, exhibitorData) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.updateExhibitor(id, exhibitorData)
      
      if (response.success) {
        const updatedExhibitor = response.exhibitor
        
        // Update in the list
        const index = exhibitors.value.findIndex(e => e.id === id)
        if (index !== -1) {
          exhibitors.value[index] = updatedExhibitor
        }
        
        // Update current exhibitor if it's the same
        if (currentExhibitor.value && currentExhibitor.value.id === id) {
          currentExhibitor.value = updatedExhibitor
        }
        
        return updatedExhibitor
      } else {
        throw new Error(response.error || 'Failed to update exhibitor')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error updating exhibitor:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const deleteExhibitor = async (id) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.deleteExhibitor(id)
      
      if (response.success) {
        // Remove from the list
        exhibitors.value = exhibitors.value.filter(e => e.id !== id)
        
        // Clear current exhibitor if it's the same
        if (currentExhibitor.value && currentExhibitor.value.id === id) {
          currentExhibitor.value = null
        }
      } else {
        throw new Error(response.error || 'Failed to delete exhibitor')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error deleting exhibitor:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const regenerateExhibitorKey = async (id) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.regenerateKey(id)
      
      if (response.success) {
        const updatedExhibitor = response.exhibitor
        
        // Update in the list
        const index = exhibitors.value.findIndex(e => e.id === id)
        if (index !== -1) {
          exhibitors.value[index] = { ...exhibitors.value[index], key: updatedExhibitor.key }
        }
        
        // Update current exhibitor if it's the same
        if (currentExhibitor.value && currentExhibitor.value.id === id) {
          currentExhibitor.value = { ...currentExhibitor.value, key: updatedExhibitor.key }
        }
        
        return updatedExhibitor.key
      } else {
        throw new Error(response.error || 'Failed to regenerate key')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error regenerating key:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const fetchLeadStats = async (exhibitorId) => {
    try {
      const response = await exhibitorApi.getLeadStats(exhibitorId)
      
      if (response.success) {
        leadStats.value = response.stats
      } else {
        throw new Error(response.error || 'Failed to fetch lead stats')
      }
    } catch (err) {
      console.error('Error fetching lead stats:', err)
    }
  }

  const fetchRecentLeads = async (exhibitorId, limit = 10) => {
    try {
      const response = await exhibitorApi.getRecentLeads(exhibitorId, limit)
      
      if (response.success) {
        recentLeads.value = response.leads || []
      } else {
        throw new Error(response.error || 'Failed to fetch recent leads')
      }
    } catch (err) {
      console.error('Error fetching recent leads:', err)
    }
  }

  const exportLeads = async (exhibitorId, format = 'csv') => {
    try {
      const response = await exhibitorApi.exportLeads(exhibitorId, format)
      
      if (response.success) {
        // Handle file download
        const blob = new Blob([response.data], { 
          type: format === 'csv' ? 'text/csv' : 'application/json' 
        })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `exhibitor-${exhibitorId}-leads.${format}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
      } else {
        throw new Error(response.error || 'Failed to export leads')
      }
    } catch (err) {
      console.error('Error exporting leads:', err)
      throw err
    }
  }

  const searchExhibitors = async (query, filters = {}) => {
    const params = {
      search: query,
      ...filters
    }
    
    return await fetchExhibitors(params)
  }

  const bulkUpdateExhibitors = async (exhibitorIds, updates) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await exhibitorApi.bulkUpdate(exhibitorIds, updates)
      
      if (response.success) {
        // Update exhibitors in the list
        exhibitorIds.forEach(id => {
          const index = exhibitors.value.findIndex(e => e.id === id)
          if (index !== -1) {
            exhibitors.value[index] = { ...exhibitors.value[index], ...updates }
          }
        })
        
        return response.updated
      } else {
        throw new Error(response.error || 'Failed to bulk update exhibitors')
      }
    } catch (err) {
      error.value = err.message
      console.error('Error bulk updating exhibitors:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  const clearError = () => {
    error.value = null
  }

  const clearCurrentExhibitor = () => {
    currentExhibitor.value = null
  }

  const setCurrentExhibitor = (exhibitor) => {
    currentExhibitor.value = exhibitor
  }

  // Reset store state
  const $reset = () => {
    exhibitors.value = []
    currentExhibitor.value = null
    leadStats.value = null
    recentLeads.value = []
    loading.value = false
    error.value = null
    pagination.value = {
      page: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0
    }
  }

  return {
    // State
    exhibitors,
    currentExhibitor,
    leadStats,
    recentLeads,
    loading,
    error,
    pagination,
    
    // Getters
    activeExhibitors,
    featuredExhibitors,
    exhibitorById,
    totalLeads,
    
    // Actions
    fetchExhibitors,
    fetchExhibitor,
    createExhibitor,
    updateExhibitor,
    deleteExhibitor,
    regenerateExhibitorKey,
    fetchLeadStats,
    fetchRecentLeads,
    exportLeads,
    searchExhibitors,
    bulkUpdateExhibitors,
    clearError,
    clearCurrentExhibitor,
    setCurrentExhibitor,
    $reset
  }
})