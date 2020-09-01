<template lang="pug">
prompt.c-profile-prompt(:allowCancel="!!user.profile.display_name", :class="classes", @close="$emit('close')")
	transition(name="profile-prompt", mode="out-in")
		.content.avatar-changer(v-if="showAvatarChanger", key="avatarChanger")
			.changer-inner
				.inputs
					bunt-button.btn-randomize randomize
					p or
					upload-button.btn-upload(@change="fileSelected", accept="image/png, image/jpg") upload
					//- bunt-button(@click="uploadAvatar") upload
				.image-wrapper
					cropper(v-if="avatarImage", ref="cropper", classname="cropper", stencil-component="circle-stencil", :src="avatarImage", :stencil-props="{aspectRatio: '1/1'}")
					identicon(v-else, :id="identicon || user.id")
			.actions
				bunt-button#btn-cancel(@click="showAvatarChanger = false") cancel
				bunt-button#btn-save(@click="uploadAvatar") {{ avatarImage ? 'upload' : 'save' }}
		.content(v-else)
			template(v-if="true || !user.profile.display_name")
				h1 {{ $t('ProfilePrompt:headline:text') }}
				p {{ $t('ProfilePrompt:intro:text') }}
			.profile
				.avatar
					img.gravatar-avatar(v-if="profileImage", :src="profileImage")
					img.gravatar-avatar(v-else-if="gravatarAvatarUrl", :src="gravatarAvatarUrl")
					identicon(v-else, :id="identicon || user.id", @click.native="changeIdenticon")
					bunt-button#btn-change-image(@click="showAvatarChanger = true") change image
				form(@submit.prevent="update")
					bunt-input.display-name(name="displayName", :label="$t('ProfilePrompt:displayname:label')", v-model.trim="displayName", :validation="$v.displayName")
					bunt-button#btn-join-world(@click="update", :loading="loading") {{ !user.profile.display_name ? $t('ProfilePrompt:create:label') : $t('ProfilePrompt:save:label') }}
			//- link here not strictly good UX
			//- a.gravatar-connected-hint(v-if="connectedGravatar", href="#", @click="connectedGravatar = false; showConnectGravatar = true") {{ $t('ProfilePrompt:gravatar-change:label') }}
			//- p.gravatar-hint(v-else-if="!showConnectGravatar") {{ $t('ProfilePrompt:gravatar-hint:text') }} #[a(href="#", @click="showConnectGravatar = true") gravatar].
			//- form.connect-gravatar(v-else, @submit.prevent="connectGravatar")
			//- 	bunt-input(name="gravatar", :label="$t('ProfilePrompt:gravatar-email:label')", :hint="$t('ProfilePrompt:gravatar-email:hint')", v-model="email")
			//- 	bunt-button#btn-connect-gravatar(@click="connectGravatar", :loading="searchingGravatar", :error="gravatarError") {{ $t('ProfilePrompt:gravatar-connect:label') }}

</template>
<script>
import { mapState } from 'vuex'
import { v4 as uuid } from 'uuid'
import { Cropper, CircleStencil } from 'vue-advanced-cropper'
import { required } from 'buntpapier/src/vuelidate/validators'
import api from 'lib/api'
import Prompt from 'components/Prompt'
import Identicon from 'components/Identicon'
import UploadButton from 'components/UploadButton'
import { getHash, getProfile, getAvatarUrl } from 'lib/gravatar'

const MAX_AVATAR_SIZE = 128

export default {
	components: { Cropper, CircleStencil, Prompt, Identicon, UploadButton },
	data () {
		return {
			displayName: '',
			identicon: null,
			profileImage: null,
			email: '',
			showAvatarChanger: false,
			showConnectGravatar: false,
			searchingGravatar: false,
			connectedGravatar: false,
			gravatarError: null,
			gravatarAvatarUrl: null,
			gravatarHash: null,
			loading: false,

			avatarFile: null,
			avatarImage: null,
		}
	},
	validations: {
		displayName: {
			required: required('Display name cannot be empty')
		}
	},
	computed: {
		...mapState(['user']),
		classes () {
			return {
				'has-avatar-changer': this.showAvatarChanger
			}
		}
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
		fileSelected () {
			// TODO block reupload while running?
			if (!event.target.files.length === 1) return
			this.avatarFile = event.target.files[0]
			const reader = new FileReader()
			reader.readAsDataURL(this.avatarFile)
			reader.onload = event => {
				if (event.target.readyState !== FileReader.DONE) return
				this.avatarImage = event.target.result
			}
		},
		uploadAvatar () {
			const { canvas } = this.$refs.cropper.getResult()
			if (canvas) {
				const resizeCanvas = document.createElement('canvas')
				resizeCanvas.width = MAX_AVATAR_SIZE
				resizeCanvas.height = MAX_AVATAR_SIZE

				var ctx = resizeCanvas.getContext('2d')
				ctx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 0, 0, MAX_AVATAR_SIZE, MAX_AVATAR_SIZE)
				resizeCanvas.toBlob(blob => {
					console.log(blob)
					const request = api.uploadFile(blob, 'avatar.png')
					request.addEventListener('load', (event) => {
						const response = JSON.parse(request.responseText)
						console.log(response)
						this.profileImage = response.url
						this.showAvatarChanger = false
					})
				}, 'image/png') // TODO use original mimetype
			}
		},
		closeAvatarChooser () {
			this.showAvatarChanger = false
			this.avatarImage = null
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
	.prompt-wrapper
		height: 386px
		width: 480px
		transition: height .2s ease, width .2s ease
	&.has-avatar-changer .prompt-wrapper
		height: 600px
		width: 640px
	.content
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		position: relative
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
		h1
			margin: 0
		p
			max-width: 360px
			display: -webkit-box
			-webkit-line-clamp: 3
			-webkit-box-orient: vertical
			overflow: hidden
		.profile
			margin: 16px 0 0 0
			display: flex
			align-items: center
		.avatar
			display: flex
			flex-direction: column
			justify-content: center
			align-items: center
			margin: 0 16px 32px 0
		.gravatar-avatar
			height: 128px
			width: 128px
			border-radius: 50%
		.c-identicon
			cursor: pointer
			height: 128px
			width: 128px
		#btn-change-image
			margin-top: 8px
			themed-button-secondary()
		form
			display: flex
			flex-direction: column
			align-items: flex-end
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
	.avatar-changer
		align-self: stretch
		align-items: stretch
		flex: auto
		padding: 32px
		.changer-inner
			flex: auto
			display: flex
			flex-direction: column
			justify-content: space-between
			align-items: center
		.inputs
			display: flex
			align-items: center
			p
				margin: 0 28px 0 16px
		.btn-randomize
			themed-button-secondary()
		.btn-upload .bunt-button
			themed-button-primary()
		.image-wrapper
			flex: auto
			display: flex
			flex-direction: column
			align-items: center
			justify-content: center
		.cropper
			width: 320px
			height: 320px
			background-color: $clr-grey-900
		.actions
			align-self: stretch
			display: flex
			justify-content: flex-end
		#btn-cancel
			themed-button-secondary()
		#btn-save
			themed-button-primary()
	.profile-prompt-enter-active, .profile-prompt-leave-active
		transition: opacity .2s ease
	.profile-prompt-enter, .profile-prompt-leave-to
		opacity: 0
</style>
