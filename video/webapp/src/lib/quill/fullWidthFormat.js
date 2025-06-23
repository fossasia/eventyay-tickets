import Quill from 'quill'

const Parchment = Quill.import('parchment')

export default new Parchment.Attributor.Class('full-width', 'ql-full-width', {scope: Parchment.Scope.BLOCK})
