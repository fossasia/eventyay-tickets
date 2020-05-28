<template lang="pug">
.c-profile-prompt
	.prompt-wrapper(v-scrollbar.y="")
		.prompt-wrapper-inner
			bunt-icon-button#btn-close(v-if="user.profile.display_name", @click="$emit('close')") close
			template(v-if="!user.profile.display_name")
				h1 {{ $t('ProfilePrompt:headline:text') }}
				p {{ $t('ProfilePrompt:intro:text') }}
			.profile
				.avatar
					img.gravatar-avatar(v-if="gravatarAvatarUrl", :src="gravatarAvatarUrl")
					identicon(v-else, :id="identicon || user.id", @click.native="changeIdenticon")
				form(@submit.prevent="update")
					bunt-input.display-name(name="displayName", :label="$t('ProfilePrompt:displayname:label')", v-model="displayName", :validation="$v.displayName")
			//- link here not strictly good UX
			a.gravatar-connected-hint(v-if="connectedGravatar", href="#", @click="connectedGravatar = false; showConnectGravatar = true") {{ $t('ProfilePrompt:gravatar-change:label') }}
			p.gravatar-hint(v-else-if="!showConnectGravatar") {{ $t('ProfilePrompt:gravatar-hint:text') }} #[a(href="#", @click="showConnectGravatar = true") gravatar].
			form.connect-gravatar(v-else, @submit.prevent="connectGravatar")
				bunt-input(name="gravatar", :label="$t('ProfilePrompt:gravatar-email:label')", :hint="$t('ProfilePrompt:gravatar-email:hint')", v-model="email")
				bunt-button#btn-connect-gravatar(@click="connectGravatar", :loading="searchingGravatar", :error="gravatarError") {{ $t('ProfilePrompt:gravatar-connect:label') }}
			bunt-button#btn-join-world(@click="update", :loading="loading") {{ !user.profile.display_name ? $t('ProfilePrompt:create:label') : $t('ProfilePrompt:save:label') }}
</template>
<script>
import { mapState } from 'vuex'
import { v4 as uuid } from 'uuid'
import { required } from 'buntpapier/src/vuelidate/validators'
import Identicon from 'components/Identicon'
import { getHash, getProfile, getAvatarUrl } from 'lib/gravatar'

export default {
	components: { Identicon },
	data () {
		return {
			displayName: '',
			identicon: null,
			email: '',
			showConnectGravatar: false,
			searchingGravatar: false,
			connectedGravatar: false,
			gravatarError: null,
			gravatarAvatarUrl: null,
			gravatarHash: null,
			loading: false
		}
	},
	validations: {
		displayName: {
			required: required('Display name cannot be empty')
		}
	},
	computed: {
		...mapState(['user'])
	},
	created () {
		if (this.user.profile.display_name) {
			this.displayName = this.user.profile.display_name
		}
		if (this.user.profile.gravatar_hash) {
			this.gravatarHash = this.user.profile.gravatar_hash
			this.gravatarAvatarUrl = getAvatarUrl(this.gravatarHash, 128)
		}
		if (this.user.profile.identicon) {
			this.identicon = this.user.profile.identicon
		}
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		changeIdenticon () {
			this.identicon = uuid()
		},
		async connectGravatar () {
			this.searchingGravatar = true
			const hash = getHash(this.email)
			const avatarUrl = getAvatarUrl(hash, 128)
			try {
				// gravatar docs say profile only works on primary email, which I think is a lie, but let's check for an image separately anyways
				const avatarResponse = await fetch(avatarUrl)
				if (avatarResponse.status !== 200) {
					// no gravatar
					this.searchingGravatar = false
					this.gravatarError = true
					return
				}
				const profile = await getProfile(hash)
				if (profile?.entry?.length > 0) {
					this.gravatarHash = profile.entry[0].hash
					this.gravatarAvatarUrl = getAvatarUrl(this.gravatarHash, 128)
					this.displayName = profile.entry[0].displayName
				} else {
					this.gravatarHash = getHash(this.email)
					this.gravatarAvatarUrl = avatarUrl
				}
				this.connectedGravatar = true
			} catch (e) {
				this.gravatarError = e
			}
			this.searchingGravatar = false
		},
		async update () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			const profile = {
				display_name: this.displayName,
			}
			if (this.gravatarHash) {
				profile.gravatar_hash = this.gravatarHash
			} else if (this.identicon) {
				profile.identicon = this.identicon
			}
			this.loading = true
			await this.$store.dispatch('updateUser', {profile})
			// TODO error handling
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-profile-prompt
	position: fixed
	top: 0
	left: 0
	width: 100vw
	height: var(--vh100)
	z-index: 1000
	background-color: $clr-secondary-text-light
	display: flex
	justify-content: center
	align-items: center
	.prompt-wrapper
		card()
		display: flex
		flex-direction: column
		width: 480px
		max-height: 80vh
		.prompt-wrapper-inner
			display: flex
			flex-direction: column
			align-items: center
			padding: 32px
			position: relative
			#btn-close
				icon-button-style(style: clear)
				position: absolute
				top: 8px
				right: 8px
			h1
				margin: 0
			p
				max-width: 320px
			.profile
				margin: 16px 0 0 0
				display: flex
				align-items: center
			.avatar
				width: 128px
				height: 128px
				margin-right: 16px
			.gravatar-avatar
				height: 128px
				border-radius: 50%
			.c-identicon
				cursor: pointer
				height: 128px
			.display-name
				width: 240px
			.gravatar-hint
				color: $clr-secondary-text-light
			.gravatar-hint, .gravatar-connected-hint
				margin-bottom: 16px
			.connect-gravatar
				display: flex
				align-items: flex-start
				margin: 16px 0 32px 0
				.bunt-input
					width: 286px
				#btn-connect-gravatar
					themed-button-secondary()
					margin: 16px 0 0 4px
			#btn-join-world
				margin-top: 16px
				themed-button-primary(size: large)
</style>
