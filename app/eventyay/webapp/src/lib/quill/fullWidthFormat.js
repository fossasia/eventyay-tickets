import Quill from 'quill'

const Parchment = Quill.import('parchment')

// Use the ClassAttributor API from Parchment (works across Quill/Parchment builds)
export default new Parchment.ClassAttributor('full-width', 'ql-full-width', {scope: Parchment.Scope.BLOCK})
