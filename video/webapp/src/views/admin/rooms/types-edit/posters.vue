<template lang="pug">
.c-poster-settings
	h2 Categories
	.categories
		.category(v-for="category of module.config.categories")
			.id {{ category.id }}
			bunt-input.label(name="label", v-model="category.label", @input="generateId(category)")
			bunt-icon-button(@click="removeCategory(category)") delete-outline
		bunt-button.btn-add(@click="addCategory") Add Category
	h2 Tags
	.tags
		.tag(v-for="tag of module.config.tags")
			.id {{ tag.id }}
			bunt-input.label(name="label", v-model="tag.label", @input="generateId(tag)")
			bunt-icon-button(@click="removeTag(tag)") delete-outline
		bunt-button.btn-add(@click="addTag") Add Tag
</template>
<script>
import mixin from './mixin'

export default {
	mixins: [mixin],
	data () {
		return {
		}
	},
	computed: {
		module () {
			return this.modules['poster.native']
		}
	},
	methods: {
		addCategory () {
			if (!this.module.config.categories) this.$set(this.module.config, 'categories', [])
			this.module.config.categories.push({
				new: true, // mark as new to autogenerate id
				id: '',
				label: ''
			})
		},
		removeCategory (category) {
			this.module.config.categories.splice(this.module.config.categories.indexOf(category), 1)
		},
		addTag () {
			if (!this.module.config.tags) this.$set(this.module.config, 'tags', [])
			this.module.config.tags.push({
				new: true, // mark as new to autogenerate id
				id: '',
				label: '',
				color: ''
			})
		},
		removeTag (tag) {
			this.module.config.tags.splice(this.module.config.tags.indexOf(tag), 1)
		},
		generateId (item) {
			if (!item.new) return
			item.id = item.label.toLowerCase().replaceAll(' ', '-')
		},
		beforeSave () {
			const stripNew = function (list) {
				for (const item of list || []) {
					delete item.new
				}
			}
			stripNew(this.module.config.categories)
			stripNew(this.module.config.tags)
		}
	}
}
</script>
<style lang="stylus">
.c-poster-settings
	.categories, .tags
		display: flex
		flex-direction: column
	.category, .tag
		display: flex
		align-items: baseline
		.id
			flex: none
			width: 35%
			color: $clr-secondary-text-light
		.label
			flex: auto
			input-style(size: compact)
	.btn-add
		align-self: flex-start
		margin-top: 8px
</style>
