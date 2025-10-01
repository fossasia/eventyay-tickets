const handleTokenTable = () => {
    const table = document.querySelector('#create-token #permission-endpoints')
    const presetField = document.querySelector('#id_permission_preset')
    table.style.display = (presetField.value === 'custom') ? 'flex' : 'none'
}
const setupTokenTable = () => {
    const presetField = document.querySelector('#id_permission_preset')
    presetField.addEventListener('change', handleTokenTable)
    handleTokenTable()
}

onReady(setupTokenTable)
