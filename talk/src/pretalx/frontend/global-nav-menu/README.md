# Global Nav Menu

A dropdown menu to navigate to Eventyay components (Tickets, Talk).

It is a Vue 3 + TypeScript subproject, built with Vite.

It is developped independently from Django system most of time. To preview, run:

```
npm run dev
```

After building (with `npm run build` command), the output files can be loaded in Django templates, via `<link>` and `<script>` tags. To know which HTML code to use for Django templates, look into the _dist/index.html_ file. For example, Vite inject this snippet to the _dist/index.html_ file:

```html
<script type="module" crossorigin src="/js/global-nav-menu.js"></script>
<link rel="stylesheet" crossorigin href="/css/global-nav-menu.index.css">
```

Then we can add it in the Django templates (note, the `type='module'` must be kept):

```html
<link rel="stylesheet" crossorigin href="{% static 'css/global-nav-menu.index.css' %}" />
<script type="module" src="{% static 'js/global-nav-menu.js' %}"></script>
```
