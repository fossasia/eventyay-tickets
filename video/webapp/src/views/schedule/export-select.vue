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
            v-if="hoveredOption === option"
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

<script>
import QRCode from 'qrcode'
import config from 'config'

export default {
	props: {
		options: {
			type: Array,
			required: true
		}
	},
  emits: ['input', 'update:modelValue'],
	data() {
		return {
			isOpen: false,
			selectedOption: null,
			hoveredOption: null,
			qrCodes: {}
		}
	},
	mounted() {
		document.addEventListener('click', this.outsideClick)
	},
  beforeUnmount() {
		document.removeEventListener('click', this.outsideClick)
	},
	created() {
		this.options.forEach(option => {
			this.generateQRCode(option)
		})
	},
	methods: {
		selectOption(option) {
			this.selectedOption = option.label
			this.isOpen = false
			this.$emit('input', option)
		},
		outsideClick(event) {
			const dropdown = this.$refs.dropdown
			if (!dropdown.contains(event.target)) {
				this.isOpen = false
			}
		},
		generateQRCode(option) {
			if (!['ics', 'xml', 'myics', 'myxml'].includes(option.id)) {
				return
			}
			const url = config.api.base + 'export-talk?export_type=' + option.id
			QRCode.toDataURL(url, { scale: 1 }, (err, url) => {
				if (!err) this.qrCodes[option.id] = url
			})
		},
		setHoveredOption(option) {
			if (['ics', 'xml', 'myics', 'myxml'].includes(option.id)) {
				this.hoveredOption = option
			} else {
				this.hoveredOption = null
			}
		},
		clearHoveredOption(option) {
			if (this.hoveredOption === option) {
				this.hoveredOption = null
			}
		},
	}
}
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
</style>
