# webapp

## Project setup
```
npm install
```

### Compiles and hot-reloads for development
```
npm start
```

### Compiles and minifies for production
```
npm run build
```

### Lints and fixes files
```
npm run lint
```

### Find missing i18n entries
```
npm run i18n:report
```

## Folder structure
```
┣━━ public: static files
┃   ┣━━ index.html: template for the static html file
┣━━ src: all the code
┃   ┣━━ assets: referenced files
┃   ┣━━ components: reusable vue components
┃   ┣━━ lib: plain js modules
┃   ┣━━ locales: translations
┃   ┣━━ router: all the routes
┃   ┣━━ store: vuex store, mutators, getters, etc
┃   ┣━━ styles: global styles and stylus modules
┃   ┣━━ views: vue components for specific routes (folder structure follows route url)
┃   ┣━━ App.vue: base layout for everything
┃   ┣━━ preloader.js: detects old browsers and small devices without loading the whole app
┃   ┣━━ i18n.js: translation loader
┃   ┣━━ main.js: app entry point
┃   ┣━━ theme.js: theme loader
```

## Conventions

We use three languages:

### JavaScript
Currently ES2015 and Stage-3 features, as provided by babel.  
Linting is done with Eslint and a slightly customized standard.js.  
Listen to the Linter.

### Pug/Jade Templates
Pug compiles down to HTML.
Vue templates are all in jade/pug.  
Has no linting.

#### Pug guide
Always use `.class` and `#id` for static defines.

Right:
```
button#btn-save.active
```
Wrong:
```
button(id="btn-save", class="active")
```

Always use vue binding shorthands `:` and `@` instead of `v-bind:` and `v-on:`

Set html attributes in the following order (first to last):
- `v-if` / `v-show`
- `v-for`
- `key`
- `:id`
- `:class`
- `:style`
- `v-model`
- `:value`
- component props
- event bindings

Avoid trailing whitespaces by using tag interpolation:
```
p This is an #[a(href="#") inline link] with spaces around it.
```

### Stylus
Stylus is a preprocessor for CSS, like SASS or LESS.  
Has no linter.

#### Stylus guide
- don't use `{} or ;`
- use `: ` between property and value
- prefix variables with `$`

#### Stylus example
```stylus
nav.toolbar
	/*flex 1*/
	card()
	height: 52px
	z-index: 100
	background-color: $ax-primary

	.top-container
		display: flex
		justify-content: space-between

	.actions
		display: flex
		align-items: center
		margin-right: 16px

	h1
		color: $clr-primary-text-dark
		margin: 8px 16px
		font-size: 20px
		font-weight: 300

		.name
			font-weight: 400
```

#### CSS guide
- Use only px, % and viewport units.
- Prefer `flex: none` and `flex: auto` before other `flex`, `flex-shrink`, `flex-grow`, `flex-basis` properties.

#### z-index ranges

0-100: page content
100: top navbar (mobile)
101: background media source
102-799: FREE
800-899: blocking popovers (emoji picker, chat user card)
900-999: expanded rooms sidebar (mobile)
1000+:  / full page overlays / prompts


#### How to name classes
- Use `.c-` or `.v-` prefix for root component / view.
- Use `.ui-` prefix (or invent a new one) for shared utility classes.
- For complex utilities, use stylus mixins.
- Prefer semantic naming (`.user` instead of `.flex-item`).


#### How to Find Color Variables
Colors are prefixed with `$clr-`.
Find existing colors from:
- https://github.com/rashfael/buntpapier/blob/master/buntpapier/variables.styl
- https://github.com/rashfael/buntpapier/blob/master/buntpapier/colors.styl (mapping https://www.materialui.co/colors)
- for text colors, use `$clr-[primary,secondary,disabled,dividers]-text-[light,dark]` (These greys are defined with alpha on black or white and work better on various backgrounds, use `light` for light backgrounds and `dark` for dark backgrounds)

### Icons
We use 'Material Design Icons'

https://materialdesignicons.com/


### Vue Files
`.vue` files combine ES, jade template and stylus sheets into one file.  
The template gets used as component templates.  
The stylus sheet is NOT scoped, so ALWAYS use a fitting root selector (for example the component root element class).
