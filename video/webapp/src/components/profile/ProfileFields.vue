<template lang="pug">
.c-profile-fields(v-if="fields")
	.field(v-for="field of fields")
		a.link(v-if="field.type === 'link'", :href="field.value", :title="field.label", target="_blank")
			.mdi.mdi-link-variant(:class="`mdi-${field.network}`")
			span {{ getLinkLabel(field) }}
		template(v-else)
			.label {{ field.label }}
			.value {{ field.value }}
</template>
<script>
import { mapState } from 'vuex'

const NETWORK_LABEL_GENERATORS = {
	twitter: {
		regex: /twitter\.com\/(.*?)\/*$/,
		generateLabel: (match) => `@${match[1]}`
	},
	linkedin: {
		regex: /linkedin\.com\/in\/(.*?)\/*$/
	},
	github: {
		regex: /github\.com\/(.*)/
	},
	facebook: {
		regex: /facebook\.com\/(.*)/
	},
	instagram: {
		regex: /instagram\.com\/(.*)/
	}
}

export default {
	props: {
		user: Object
	},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['world']),
		fields () {
			if (!this.user.profile?.fields) return
			return this.world?.profile_fields
				.map(field => ({...field, value: this.user.profile.fields[field.id]}))
				.filter(field => !!field.value)
		},
	},
	methods: {
		getLinkLabel (field) {
			const generator = NETWORK_LABEL_GENERATORS[field.network]
			if (!generator) return field.value
			const match = field.value.match(generator.regex)
			if (!match) return field.value
			return generator.generateLabel?.(match) || match[1]
		}
	}
}
</script>
<style lang="stylus">
.c-profile-fields
	display: flex
	flex-direction: column
	.field
		flex: none
		display: flex
		a.link
			display: flex
			align-items: center
			margin-bottom: 4px
			.mdi
				font-size: 24px
				margin-right: 4px
// hack specificity to create fallback icon for things not in mdi
:where(.c-profile-fields a.link .mdi)::before
	content: "\F0339"
</style>
