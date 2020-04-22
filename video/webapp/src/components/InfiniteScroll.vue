<template lang="pug">
.c-infinite-scroll
	slot(v-if="loading")
		bunt-progress-circular(size="huge", :page="true")
</template>
<script>
export default {
	props: {
		loading: Boolean
	},
	data () {
		return {
			isIntersecting: false
		}
	},
	watch: {
		loading () {
			if (!this.loading && this.isIntersecting) this.$emit('load')
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.observer = new IntersectionObserver(this.intersected)
		this.observer.observe(this.$el)
	},
	methods: {
		intersected (event) {
			this.isIntersecting = event[0].isIntersecting
			if (!this.loading && this.isIntersecting) this.$emit('load')
		}
	}
}
</script>
<style lang="stylus">
</style>
