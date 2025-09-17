import axios from 'axios'

// Create axios instance with base configuration
const api = axios.create({
  baseURL: '/api/v1/exhibitors/',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  }
})

// Request interceptor to add CSRF token
api.interceptors.request.use(
  (config) => {
    // Add CSRF token if available
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                     document.querySelector('meta[name=csrf-token]')?.getAttribute('content')
    
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken
    }
    
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    
    // Handle different error types
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response
      
      switch (status) {
        case 401:
          // Unauthorized - redirect to login or show auth error
          window.location.href = '/auth/login/'
          break
        case 403:
          // Forbidden
          throw new Error(data.error || 'Access denied')
        case 404:
          // Not found
          throw new Error(data.error || 'Resource not found')
        case 422:
          // Validation error
          throw new Error(data.error || 'Validation failed')
        case 500:
          // Server error
          throw new Error('Server error. Please try again later.')
        default:
          throw new Error(data.error || `HTTP ${status} error`)
      }
    } else if (error.request) {
      // Network error
      throw new Error('Network error. Please check your connection.')
    } else {
      // Other error
      throw new Error(error.message || 'An unexpected error occurred')
    }
  }
)

export const exhibitorApi = {
  // Get all exhibitors
  async getExhibitors(params = {}) {
    const queryParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        queryParams.append(key, params[key])
      }
    })
    
    const queryString = queryParams.toString()
    const url = queryString ? `exhibitors/?${queryString}` : 'exhibitors/'
    
    return await api.get(url)
  },

  // Get single exhibitor
  async getExhibitor(id) {
    return await api.get(`exhibitors/${id}/`)
  },

  // Create new exhibitor
  async createExhibitor(exhibitorData) {
    // Handle file upload if logo is present
    if (exhibitorData.logo && exhibitorData.logo instanceof File) {
      const formData = new FormData()
      
      Object.keys(exhibitorData).forEach(key => {
        if (exhibitorData[key] !== null && exhibitorData[key] !== undefined) {
          formData.append(key, exhibitorData[key])
        }
      })
      
      return await api.post('exhibitors/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
    }
    
    return await api.post('exhibitors/', exhibitorData)
  },

  // Update exhibitor
  async updateExhibitor(id, exhibitorData) {
    // Handle file upload if logo is present
    if (exhibitorData.logo && exhibitorData.logo instanceof File) {
      const formData = new FormData()
      
      Object.keys(exhibitorData).forEach(key => {
        if (exhibitorData[key] !== null && exhibitorData[key] !== undefined) {
          formData.append(key, exhibitorData[key])
        }
      })
      
      return await api.put(`exhibitors/${id}/`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
    }
    
    return await api.put(`exhibitors/${id}/`, exhibitorData)
  },

  // Delete exhibitor (soft delete)
  async deleteExhibitor(id) {
    return await api.delete(`exhibitors/${id}/`)
  },

  // Regenerate exhibitor access key
  async regenerateKey(id) {
    return await api.post(`exhibitors/${id}/regenerate-key/`)
  },

  // Get exhibitor lead statistics
  async getLeadStats(exhibitorId) {
    return await api.get(`exhibitors/${exhibitorId}/stats/`)
  },

  // Get recent leads for exhibitor
  async getRecentLeads(exhibitorId, limit = 10) {
    return await api.get(`exhibitors/${exhibitorId}/leads/recent/?limit=${limit}`)
  },

  // Export exhibitor leads
  async exportLeads(exhibitorId, format = 'csv') {
    const response = await api.get(`exhibitors/${exhibitorId}/leads/export/`, {
      params: { format },
      responseType: 'blob'
    })
    
    return {
      success: true,
      data: response
    }
  },

  // Bulk update exhibitors
  async bulkUpdate(exhibitorIds, updates) {
    return await api.post('exhibitors/bulk-update/', {
      exhibitor_ids: exhibitorIds,
      updates: updates
    })
  },

  // Exhibitor authentication (for mobile apps)
  async authenticateExhibitor(key) {
    return await api.post('auth/', { key })
  },

  // Get exhibitor settings
  async getSettings() {
    return await api.get('settings/')
  },

  // Update exhibitor settings
  async updateSettings(settings) {
    return await api.put('settings/', settings)
  }
}

// Lead management API
export const leadApi = {
  // Create lead from scan
  async createLead(leadData, exhibitorKey) {
    return await api.post('leads/', leadData, {
      headers: {
        'Exhibitor-Key': exhibitorKey
      }
    })
  },

  // Get leads for exhibitor
  async getLeads(exhibitorKey, params = {}) {
    const queryParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        queryParams.append(key, params[key])
      }
    })
    
    const queryString = queryParams.toString()
    const url = queryString ? `leads/list/?${queryString}` : 'leads/list/'
    
    return await api.get(url, {
      headers: {
        'Exhibitor-Key': exhibitorKey
      }
    })
  },

  // Update lead
  async updateLead(leadId, leadData, exhibitorKey) {
    return await api.post(`leads/${leadId}/`, leadData, {
      headers: {
        'Exhibitor-Key': exhibitorKey
      }
    })
  },

  // Get tags for exhibitor
  async getTags(exhibitorKey) {
    return await api.get('tags/', {
      headers: {
        'Exhibitor-Key': exhibitorKey
      }
    })
  }
}

// Utility functions
export const apiUtils = {
  // Build query string from object
  buildQueryString(params) {
    const queryParams = new URLSearchParams()
    
    Object.keys(params).forEach(key => {
      if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
        if (Array.isArray(params[key])) {
          params[key].forEach(value => queryParams.append(key, value))
        } else {
          queryParams.append(key, params[key])
        }
      }
    })
    
    return queryParams.toString()
  },

  // Handle file download from blob response
  downloadFile(blob, filename, mimeType = 'application/octet-stream') {
    const url = window.URL.createObjectURL(new Blob([blob], { type: mimeType }))
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  },

  // Format error message from API response
  formatErrorMessage(error) {
    if (typeof error === 'string') {
      return error
    }
    
    if (error.details && typeof error.details === 'object') {
      // Handle validation errors
      const messages = []
      Object.keys(error.details).forEach(field => {
        const fieldErrors = Array.isArray(error.details[field]) 
          ? error.details[field] 
          : [error.details[field]]
        
        fieldErrors.forEach(msg => {
          messages.push(`${field}: ${msg}`)
        })
      })
      return messages.join(', ')
    }
    
    return error.message || 'An unexpected error occurred'
  }
}

export default api