// Thin wrapper to make janus-gateway available as an ES module default export.
// The janus-gateway package provides a UMD/global build that attaches `Janus` to window.
// We import it for side effects, then re-export the global.
import 'janus-gateway'

const Janus = (typeof window !== 'undefined') ? window.Janus : undefined

export default Janus
