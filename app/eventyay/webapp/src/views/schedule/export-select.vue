<template>
  <div
    ref="dropdown"
    class="custom-dropdown"
  >
    <button @click="isOpen = !isOpen">
      {{ selectedOption || 'Add to Calendar' }}
    </button>
    <div
      v-if="isOpen"
      class="dropdown-options"
    >
      <div
        v-for="option in options"
        :key="option.id"
        class="dropdown-item"
        @click="selectOption(option)"
        @mouseover="setHoveredOption(option)"
        @mouseleave="clearHoveredOption(option)"
      >
        <div class="item-text">
          {{ option.label }}
        </div>
        <img
          v-if="qrCodes[option.id]"
          class="default-image"
          :src="qrCodes[option.id]"
          alt="QR Code"
        >
        <transition name="fade">
          <div
            v-if="hoveredOption === option.id"
            class="qr-popup"
          >
            <img
              :src="qrCodes[option.id]"
              alt="QR Code"
            >
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onBeforeUnmount } from 'vue'
import QRCode from 'qrcode'
import config from 'config'

const props = defineProps({
  options: {
    type: Array,
    required: true
  },
  modelValue: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['input', 'update:modelValue'])

const dropdown = ref(null)
const isOpen = ref(false)
const selectedOption = ref(props.modelValue ? props.modelValue.label : null)
const hoveredOption = ref(null)
const qrCodes = reactive({})

watch(() => props.modelValue, (newVal) => {
  selectedOption.value = newVal ? newVal.label : null
})

watch(() => props.options, (newOpts) => {
  // regenerate QR codes when options change
  for (const k in qrCodes) delete qrCodes[k]
  if (Array.isArray(newOpts)) {
    newOpts.forEach(option => generateQRCode(option))
  }
}, { immediate: true, deep: true })

function selectOption(option) {
  selectedOption.value = option.label
  isOpen.value = false
  emit('update:modelValue', option)
  emit('input', option)
}

function outsideClick(event) {
  const dd = dropdown.value
  if (dd && !dd.contains(event.target)) {
    isOpen.value = false
  }
}

async function generateQRCode(option) {
  if (!['ics', 'xml', 'myics', 'myxml'].includes(option.id)) return
  const url = config.api.base + 'export-talk?export_type=' + option.id
  // generate a larger image to avoid pixelation when scaled down
  const popupSize = 150 // CSS popup size in px
  const ratio = (typeof window !== 'undefined' && window.devicePixelRatio) ? window.devicePixelRatio : 1
  const targetWidth = Math.ceil(popupSize * Math.max(1, ratio))
  try {
    const dataUrl = await QRCode.toDataURL(url, { width: targetWidth, margin: 1, errorCorrectionLevel: 'H' })
    qrCodes[option.id] = dataUrl
  } catch (err) {
    // Keep behavior silent on error (same as previous implementation).
    // Optional: console.error('QR generation failed', err)
  }
}

function setHoveredOption(option) {
  if (['ics', 'xml', 'myics', 'myxml'].includes(option.id)) {
    hoveredOption.value = option.id
  } else {
    hoveredOption.value = null
  }
}

function clearHoveredOption(option) {
  if (hoveredOption.value === option.id) hoveredOption.value = null
}

onMounted(() => {
  document.addEventListener('click', outsideClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', outsideClick)
})
</script>

<style>
.custom-dropdown {
  position: relative;
  display: inline-block;
  z-index: 100;
  align-content: center;
}

@media screen and (min-width: 480px) {
    .custom-dropdown {
      margin-right: 100px;
    }
}

.custom-dropdown button {
  border: none;
  height: 32px;
  border-radius: 2px;
}

.dropdown-options {
  position: absolute;
  background-color: #f9f9f9;
  min-width: 180px;
  box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
  z-index: 1;
}

.dropdown-options .dropdown-item {
  display: flex;
  justify-content: space-between;
}

.dropdown-options .dropdown-item .item-text {
  align-self: flex-end;
}

.dropdown-options div {
  color: black;
  padding: 2px 2px;
  text-decoration: none;
  display: block;
}

.dropdown-options div:hover {
  background-color: #f1f1f1;
}
.fade-enter-active, .fade-leave-active {
  transition: opacity .5s;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.qr-popup {
  position: absolute;
  right: 100%;
  top: 0;
  padding: 10px;
  background: white;
  border: 1px solid #ccc;
  box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1);
}
.qr-popup img {
  width: 150px; /* Adjust as needed */
  height: 150px; /* Adjust as needed */
}

.dropdown-options .dropdown-item .default-image {
  width: 20px; /* Adjust as needed */
  height: 20px; /* Adjust as needed */
  align-self: flex-end;
}

/* Ensure QR images keep sharp edges and are not blurry when displayed */
.dropdown-options img.default-image,
.qr-popup img {
  display: block;
  object-fit: contain;
  image-rendering: -webkit-optimize-contrast; /* Safari */
  image-rendering: crisp-edges;
  image-rendering: pixelated; /* fallback */
}
</style>
