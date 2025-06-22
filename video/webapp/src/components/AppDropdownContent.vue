<template>
  <transition :name="elClass">
    <div
      v-if="active"
      :class="elClass"
      @click.stop
    >
      <slot />
    </div>
  </transition>
</template>

<script>
export default {
	name: 'AppDropdownContent',
	inject: ['sharedState'],
	props: {
		className: {
			type: String,
			default: '',
		},
	},
	computed: {
		active() {
			return this.sharedState.active
		},
		elClass() {
			return this.className ? this.className + ' dropdown-content' : 'dropdown-content'
		},
	},
}
</script>

<style>
.dropdown-content {
  position: absolute;
  margin-top: 4px;
  left: 0;
  right: 0;
  width: 100%;
  max-width: none;
  min-width: 400px;
  border: 1px solid rgba(0, 0, 0, 0.38);
  background-color: #fff;
  z-index: 1000;
  max-height: 350px;
  overflow-y: auto;
  padding-bottom: 10px;
}
.dropdown-content .checkbox-line {
  margin: 8px;
}
.dropdown-content .checkbox-line .bunt-checkbox .bunt-checkbox-box {
  min-width: 20px;
}
.dropdown-content-enter-active,
.dropdown-content-leave-active {
  transition: all 0.2s;
}
.dropdown-content-enter,
.dropdown-content-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}

.checkbox-text {
  margin-left: 10px;
  flex: 1;
  white-space: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}

@media (max-width: 480px) {
  .dropdown-content {
    width: 70vw;
    left: 5vw;
    right: auto;
    max-width: calc(100% - 40px);
    min-width: 350px;
    margin-left: -20px;
    position: fixed;
  }
}
</style>
