<template>
  <div
    v-click-away="away"
    :class="elClass"
  >
    <bunt-button @click="toggle">
      <slot name="toggler">
        Toggle
      </slot>
      <svg
        v-if="sharedState.active"
        xmlns="http://www.w3.org/2000/svg"
        width="1em"
        height="1em"
        viewBox="0 0 24 24"
      >
        <path
          fill="currentColor"
          d="m7 15l5-5l5 5z"
        />
      </svg>
      <svg
        v-else
        xmlns="http://www.w3.org/2000/svg"
        width="1em"
        height="1em"
        viewBox="0 0 24 24"
      >
        <path
          fill="currentColor"
          d="m7 10l5 5l5-5z"
        />
      </svg>
    </bunt-button>
    <slot />
  </div>
</template>

<script>
const clickAway = {
  beforeMount(el, binding) {
    el.clickOutsideEvent = function(event) {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event);
      }
    };
    document.addEventListener('click', el.clickOutsideEvent);
  },
  beforeUnmount(el) {
    document.removeEventListener('click', el.clickOutsideEvent);
  }
};

export default {
	name: 'AppDropdown',
	directives: {
		'click-away': clickAway
	},
	props: {
		className: {
			type: String,
			default: '',
		},
	},
	provide() {
		return {
			sharedState: this.sharedState
		}
	},
	data() {
		return {
			sharedState: {
				active: false,
			},
		}
	},
	computed: {
		elClass() {
			return this.className ? this.className + ' app-drop-down' : 'app-drop-down'
		},
	},
	methods: {
		toggle() {
			this.sharedState.active = !this.sharedState.active
		},
		away() {
			this.sharedState.active = false
		}
	}
}
</script>

<style>
.app-drop-down {
    margin: 12px 4px 12px 14px;
    border-radius: 5px;
    border: 2px solid rgba(0, 0, 0, 0.38);
}
.app-drop-down .bunt-button {
    background-color: white;
}
.app-drop-down .bunt-button .bunt-button-content {
    text-transform: capitalize;
}
</style>
