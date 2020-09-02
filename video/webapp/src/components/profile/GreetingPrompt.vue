<template lang="pug">
prompt.c-profile-greeting-prompt(:allowCancel="false")
	.content
		connect-gravatar(v-if="showConnectGravatar", @change="setGravatar")
		.step-display-name(v-if="activeStep === 'displayName'")
			h1 Salutations!
			p Sorry, can't let you without seeing some ID first.
			//- link here not strictly good UX
			a.gravatar-connected-hint(v-if="connectedGravatar", href="#", @click="connectedGravatar = false; showConnectGravatar = true") {{ $t('ProfilePrompt:gravatar-change:label') }}
			p.gravatar-hint(v-else-if="!showConnectGravatar") {{ $t('ProfilePrompt:gravatar-hint:text') }} #[a(href="#", @click="showConnectGravatar = true") gravatar].
			bunt-input.display-name(name="displayName", :label="$t('ProfilePrompt:displayname:label')", v-model.trim="profile.display_name", :validation="$v.profile.display_name")
		.step-avatar(v-else-if="activeStep === 'avatar'")
			h1 Next, add some color!
			p bla bla stuff?
			change-avatar(ref="step", v-model="profile.avatar")
		.step-additional-fields(v-else-if="activeStep === 'additionalFields'")
			h1 Finally, fields!
			p Some nosy people want to know more about you
			change-additional-fields(v-model="profile.fields")
		.actions
			bunt-button#btn-back(v-if="previousStep", @click="activeStep = previousStep") back
			bunt-button#btn-continue(v-if="nextStep", :class="{invalid: $v.$invalid && $v.$dirty}", :disabled="$v.$invalid && $v.$dirty", :loading="processingStep", :key="activeStep", @click="toNextStep") continue
			bunt-button#btn-finish(v-else) finish
</template>
<script>
import { mapState } from 'vuex'
import Prompt from 'components/Prompt'
import ChangeAvatar from './ChangeAvatar'
import ChangeAdditionalFields from './ChangeAdditionalFields'
import ConnectGravatar from './ConnectGravatar'
import { required } from 'buntpapier/src/vuelidate/validators'

export default {
	components: { Prompt, ChangeAvatar, ChangeAdditionalFields, ConnectGravatar },
	data () {
		return {
			activeStep: null,
			showConnectGravatar: false,
			connectedGravatar: false,
			profile: null,
			processingStep: false,
			saving: false,
		}
	},
	validations: {
		profile: {
			display_name: {
				required: required('Display name cannot be empty')
			}
		}
	},
	computed: {
		...mapState(['user']),
		steps () {
			return [
				'displayName',
				'avatar',
				'additionalFields'
			]
		},
		previousStep () {
			return this.steps[this.steps.indexOf(this.activeStep) - 1]
		},
		nextStep () {
			return this.steps[this.steps.indexOf(this.activeStep) + 1]
		}
	},
	created () {
		this.activeStep = this.steps[0]
		this.profile = Object.assign({
			display_name: '',
			avatar: {
				identicon: this.user.id
			},
			fields: {}
		}) //, this.user.profile)
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async toNextStep () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			if (this.$refs.step?.update) {
				this.processingStep = true
				await this.$refs.step.update()
				this.processingStep = false
			}
			this.activeStep = this.nextStep
		},
		setGravatar (gravatar) {

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
.c-profile-greeting-prompt
	.prompt-wrapper
		// height: 400px
		width: 480px
	.content
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		position: relative
		padding: 16px

		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
		#btn-back
			themed-button-secondary()
			margin-right: 8px
		#btn-continue, #btn-finish
			themed-button-primary()
			&.invalid
				button-style(color: $clr-danger)
</style>
