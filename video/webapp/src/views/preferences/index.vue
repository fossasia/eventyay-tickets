<template lang="pug">
.v-preferences
</template>
<script>
import ChangeAvatar from 'components/profile/ChangeAvatar'
import ChangeAdditionalFields from 'components/profile/ChangeAdditionalFields'
import ConnectGravatar from 'components/profile/ConnectGravatar'

export default {
	components: { ChangeAvatar, ChangeAdditionalFields, ConnectGravatar},
	data () {
		return {
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.v-preferences
	display: flex
	flex-direction: column
</style>
