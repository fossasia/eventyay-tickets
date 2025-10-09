// Custom Buntpapier Stylus plugin wrapper for Vite 7 compatibility
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Export as a simple object instead of a function factory to avoid cloning issues
export const buntpapierStylusPlugin = {
  name: 'buntpapier-stylus',
  setup: (style) => {
    // Add the buntpapier directory to the include path
    const buntpapierPath = path.resolve(__dirname, '../../node_modules/buntpapier')
    style.include(buntpapierPath)
  }
}
