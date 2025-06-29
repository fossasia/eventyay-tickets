<template lang="pug">
.c-iframe-blocker
	iframe(v-if="showIframe", :src="src", v-bind="$attrs")
	.consent-blocker(v-else)
		.warning This content is hosted by a third party on
		.domain {{ domain }}
		.toc(v-if="config.policy_url") By showing this external content you accept their #[a(:href="config.policy_url") terms and conditions].
		bunt-button#btn-show(@click="showOnce") Show external content
		bunt-checkbox(name="remember", v-model="remember") Remember my choice
</template>
<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import store from 'store'

defineOptions({
  inheritAttrs: false
})

const props = defineProps({
  src: String
})

const showingOnce = ref(false)
const remember = ref(false)

const domain = computed(() => {
  if (typeof props.src !== 'string') return
  return new URL(props.src).host
})

const config = computed(() => {
  console.log(store.state.world.iframe_blockers, domain.value)
  for (const [domainPattern, domainConfig] of Object.entries(store.state.world.iframe_blockers)) {
    if (domain.value === domainPattern || domain.value.endsWith('.' + domainPattern)) {
      return domainConfig
    }
  }
  return store.state.world.iframe_blockers.default
})

const showIframe = computed(() => {
  return showingOnce.value ||
    store.state.unblockedIframeDomains.has(domain.value) ||
    !config.value.enabled
})

onMounted(async () => {
  await nextTick()
})

function showOnce() {
  if (remember.value) {
    store.dispatch('unblockIframeDomain', domain.value)
  }
  showingOnce.value = true
}
</script>
<style lang="stylus">
.c-iframe-blocker
	flex: auto
	display: flex
	iframe
		height: 100%
		width: 100%
		position: absolute
		top: 0
		left: 0
		border: none
		flex: auto // because safari
	.consent-blocker
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		gap: 16px
		background-color: $clr-grey-800
		color: $clr-primary-text-dark
		.warning
			font-size: 20px
		.domain
			font-family: monospace
			font-size: 24px
		.toc
			font-size: 16px
			a
				color: $clr-primary-text-dark
				text-decoration: underline
				&:hover
					color: $clr-secondary-text-dark
		.bunt-checkbox
			label
				font-size: 20px
			&:not(.checked) .bunt-checkbox-box
				border-color: $clr-primary-text-dark
		+above('s')
			#btn-show
				margin-top: 24px
				themed-button-primary(size: large)
		+below('s')
			gap: 8px
			.warning, .domain
				font-size: 12px
			.toc
				font-size: 10px
			#btn-show
				margin-top: 8px
				themed-button-primary()
			.bunt-checkbox
				label
					font-size: 16px
</style>
