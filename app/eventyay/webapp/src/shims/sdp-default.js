// Shim to provide a default export for the 'sdp' package
// Some dependencies expect `import SDPUtils from 'sdp'`, but the package
// may not expose a default export. This wrapper normalizes that.
import * as SDP from 'sdp'
export default SDP
