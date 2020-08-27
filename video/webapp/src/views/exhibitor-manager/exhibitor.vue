<template lang="pug">
.c-manage-exhibitor
	.error(v-if="error") {{ $t('Exhibitors:exhibitor-not-found:text') }}
	template(v-else-if="exhibitor")
		.header
			bunt-icon-button(@click="$router.push({name: 'exhibitors'})") arrow_left
			h2 {{ exhibitor.name }}
			.actions
				bunt-button.btn-save(@click="save", :loading="saving") {{ $t('Exhibitors:save:label') }}
		.main-form(v-scrollbar.y="")
			bunt-input(v-model="exhibitor.name", :label="$t('Exhibitors:name:label')", name="name", :validation="$v.exhibitor.name")
			bunt-input(v-model="exhibitor.tagline", :label="$t('Exhibitors:tagline:label')", name="tagline", :validation="$v.exhibitor.tagline")
			bunt-input(v-model="exhibitor.short_text", :label="$t('Exhibitors:short-text:label')", name="shortText", :validation="$v.exhibitor.shortText")
			bunt-input-outline-container(:label="$t('Exhibitors:text:label')")
				textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="exhibitor.text")
			upload-url-input(v-model="exhibitor.logo", :label="$t('Exhibitors:logo:label')", name="logo")
			upload-url-input(v-model="exhibitor.banner_list", :label="$t('Exhibitors:banner-list:label')", name="bannerList")
			upload-url-input(v-model="exhibitor.banner_detail", :label="$t('Exhibitors:banner-detail:label')", name="bannerDetail")
			bunt-select(v-model="exhibitor.size", :label="$t('Exhibitors:size:label')", name="size", :options="sizes", :validation="$v.exhibitor.size")
			bunt-input(v-model="exhibitor.sorting_priority", :label="$t('Exhibitors:sorting-priority:label')", name="sortingPriority", :validation="$v.exhibitor.sortingPriority")
			bunt-select(v-model="exhibitor.room_id", :label="$t('Exhibitors:room:label')", name="room", :options="rooms", option-label="name", :validation="$v.exhibitor.roomId")
				template(slot-scope="{ option }")
					.label {{ option.name }}
			table.social-media-links
				thead
					tr
						th {{ $t('Exhibitors:social-media-link:label') }}
						th
						th
				tbody
					tr(v-for="(link, index) in exhibitor.social_media_links")
						td
							bunt-input(:value="link.display_text", :label="$t('Exhibitors:link-text:label')", @input="set_social_media_link_text(index, $event)", name="displayText")
						td
							bunt-input(:value="link.url", :label="$t('Exhibitors:link-url:label')", @input="set_social_media_link_url(index, $event)", name="url")
						td.actions
							bunt-icon-button(@click="remove_social_media_link(index)") delete-outline
				tfoot
					tr
						td
							bunt-button(@click="add_social_media_link") {{ $t('Exhibitors:add-link:text') }}
						td
						td
			table.links
				thead
					tr
						th {{ $t('Exhibitors:link:label') }}
						th
						th
						th
				tbody
					tr(v-for="(link, index) in exhibitor.links")
						td
							bunt-input(:value="link.display_text", :label="$t('Exhibitors:link-text:label')", @input="set_link_text(index, $event)", name="displayText")
						td
							bunt-input(:value="link.url", :label="$t('Exhibitors:link-url:label')", @input="set_link_url(index, $event)", name="url")
						td
							bunt-select(:value="link.category", :label="$t('Exhibitors:link-category:label')", @input="set_link_category(index, $event)", name="category", :options="linkCategories")
						td.actions
							bunt-icon-button(@click="remove_link(index)") delete-outline
				tfoot
					tr
						td
							bunt-button(@click="add_link") {{ $t('Exhibitors:add-link:text') }}
						td
						td
			table.staff
				thead
					tr
						th {{ $t('Exhibitors:staff:label') }}
						th
				tbody
					tr(v-for="(user, index) in exhibitor.staff")
						td.user
							avatar(:user="user", :size="36")
							span.display-name {{ user ? user.profile.display_name : '' }}
						td.actions
							bunt-icon-button(@click="remove_staff(index)") delete-outline
				tfoot
					tr
						td
							bunt-button(@click="showStaffPrompt=true") {{ $t('Exhibitors:add-staff:text') }}
						td
						td
			bunt-checkbox(v-model="exhibitor.contact_enabled", :label="$t('Exhibitors:contact-enabled:label')", name="contactEnabled")

			.danger-zone
				bunt-button.delete(icon="delete", @click="showDeletePrompt = true") {{ $t('DeletePrompt:button:label') }}
				span {{ $t('DeletePrompt:button:warning') }}
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.delete-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
			.content
				p {{ $t('DeletePrompt:confirm:text') }}
				.name {{ exhibitor.name }}
				bunt-input(name="exhibitorName", :label="$t('Exhibitors:name:label')", v-model="deletingExhibitorName")
				bunt-button.room(icon="delete", :disabled="deletingExhibitorName !== exhibitor.name", @click="deleteExhibitor", :loading="deleting", :error-message="deleteError") {{ $t('Exhibitors:delete:label') }}
	prompt.add-staff-prompt(v-if="showStaffPrompt", :scrollable="false", @close="showStaffPrompt=false")
		.content
			h1 {{ $t('Exhibitors:add-staff:text') }}
			user-select(:button-label="$t('Exhibitors:add-staff:label')", @selected="add_staff")
</template>
<script>
import api from 'lib/api'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import UserSelect from 'components/UserSelect'
import UploadUrlInput from 'components/config/UploadUrlInput'
import { required, maxLength } from 'buntpapier/src/vuelidate/validators'

export default {
	components: { Avatar, Prompt, UploadUrlInput, UserSelect },
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null,
			saving: false,
			error: null,
			showDeletePrompt: false,
			showStaffPrompt: false,
			deletingExhibitorName: '',
			deleting: false,
			deleteError: null,
			sizes: ['S', 'M', 'L'],
			linkCategories: ['profile', 'download']
		}
	},
	computed: {
		rooms: function () {
			return this.$store.state.rooms.filter(room => room.modules.filter(m => m.type === 'exhibition.native').length > 0)
		}
	},
	validations () {
		return {
			exhibitor: {
				name: {
					required: required(this.$t('Exhibitors:validation-name:required')),
					maxLength: maxLength(80, this.$t('Exhibitors:validation-name:maxLength'))
				},
				tagline: {
					maxLength: maxLength(250, this.$t('Exhibitors:validation-tagline:maxLength'))
				},
				shortText: {
					maxLength: maxLength(500, this.$t('Exhibitors:validation-short-text:maxLength'))
				},
				size: {
					required: required(this.$t('Exhibitors:validation-size:required'))
				},
				roomId: {
					required: required(this.$t('Exhibitors:validation-room:required'))
				}
			}
		}
	},
	async created () {
		try {
			if (this.exhibitorId !== '') {
				this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
			} else {
				this.exhibitor = {
					id: '',
					name: '',
					tagline: '',
					short_text: '',
					text: '',
					logo: '',
					banner_list: '',
					banner_detail: '',
					size: '',
					sorting_priority: 0,
					room_id: '',
					social_media_links: [],
					links: [],
					staff: [],
					contact_enabled: true,
				}
			}
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		remove_social_media_link (link) {
			this.$delete(this.exhibitor.social_media_links, link)
		},
		add_social_media_link () {
			this.exhibitor.social_media_links.push({display_text: '', url: ''})
		},
		set_social_media_link_text (index, displayText) {
			this.exhibitor.social_media_links[index].display_text = displayText
		},
		set_social_media_link_url (index, url) {
			this.exhibitor.social_media_links[index].url = url
		},
		remove_link (link) {
			this.$delete(this.exhibitor.links, link)
		},
		add_link () {
			this.exhibitor.links.push({display_text: '', url: '', category: ''})
		},
		set_link_text (index, displayText) {
			this.exhibitor.links[index].display_text = displayText
		},
		set_link_url (index, url) {
			this.exhibitor.links[index].url = url
		},
		set_link_category (index, category) {
			this.exhibitor.links[index].category = category
		},
		add_staff (users) {
			this.exhibitor.staff = this.exhibitor.staff.concat(users)
			this.exhibitor.staff = this.exhibitor.staff.filter((user, index) => this.exhibitor.staff.indexOf(user) === index)
			this.showStaffPrompt = false
		},
		remove_staff (user) {
			this.$delete(this.exhibitor.staff, user)
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			await api.call('exhibition.patch', {
				id: this.exhibitorId,
				name: this.exhibitor.name,
				tagline: this.exhibitor.tagline,
				short_text: this.exhibitor.short_text,
				text: this.exhibitor.text,
				logo: this.exhibitor.logo,
				banner_list: this.exhibitor.banner_list,
				banner_detail: this.exhibitor.banner_detail,
				size: this.exhibitor.size,
				sorting_priority: this.exhibitor.sorting_priority,
				room_id: this.exhibitor.room_id,
				social_media_links: this.exhibitor.social_media_links,
				links: this.exhibitor.links,
				staff: this.exhibitor.staff,
				contact_enabled: this.exhibitor.contact_enabled,
			})
			this.saving = false
			// TODO error handling
		},
		async deleteExhibitor () {
			this.deleting = true
			this.deleteError = null
			try {
				await api.call('exhibition.delete', {exhibitor: this.exhibitorId})
				this.$router.replace({name: 'exhibitors'})
			} catch (error) {
				this.deleteError = this.$t(`error:${error.code}`)
			}
			this.deleting = false
		}
	}
}
</script>
<style lang="stylus">
.c-manage-exhibitor
	display flex
	flex-direction column
	background $clr-white
	min-height 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.header
		background-color $clr-grey-100
		border-bottom border-separator()
		display flex
		padding 8px
		flex none
		.bunt-icon-button
			margin-right 8px
		h2
			flex auto
			font-size 21px
			font-weight 500
			margin 1px 16px 0 0
			ellipsis()
		.actions
			display flex
			flex none
			.bunt-button:not(:last-child)
				margin-right 16px
			.btn-save
				themed-button-primary()
	.main-form
		display flex
		flex-direction column
		> *
			margin 0 16px
		.bunt-input-outline-container
			textarea
				background-color transparent
				border none
				outline none
				resize vertical
				min-height 250px
				padding 0 8px
	h2
		margin-top 0
		margin-bottom 16px
	.social-media-links, .links, .staff
		th
			text-align left
			border-bottom 1px solid #ccc
			padding 10px
		td
			vertical-align center
		td.actions
			text-align right
		td.user
			display flex
			align-items center
			min-height 48px
			.display-name
				margin-left 8px
				flex auto
				ellipsis()

	.danger-zone
		margin 50px 8px
		color $clr-danger
		border-top 2px solid $clr-danger
		padding 8px
		.delete
			button-style(color: $clr-danger)
			margin 0 8px

	.delete-prompt
		.content
			display flex
			flex-direction column
			padding 16px
		.question-box-header
			margin-top -10px
			margin-bottom 15px
			align-items center
			display flex
			justify-content space-between
		.name
			font-family monospace
			font-size 16px
			border border-separator()
			border-radius 4px
			padding 4px 8px
			background-color $clr-grey-100
			align-self center
		.delete
			button-style(color: $clr-danger)

	.add-staff-prompt
		.prompt-wrapper
			height 80vh
			width 600px
		.content
			display flex
			flex-direction column
			position relative
			box-sizing border-box
			min-height 0
			#btn-close
				icon-button-style(style: clear)
				position absolute
				top 8px
				right 8px
			h1
				margin 0
				text-align center
			p
				max-width 320px
			form
				display flex
				flex-direction column
				align-self stretch
				.bunt-button
					themed-button-primary()
					margin-top 16px
				.bunt-select
					select-style(size: compact)
					ul li
						display flex
						.mdi
							margin-right 8px
				.bunt-input-outline-container
					textarea
						background-color transparent
						border none
						outline none
						resize vertical
						min-height 64px
						padding 0 8px
</style>
