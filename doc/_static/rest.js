const spec = "/schema.yml";
Redoc.init(spec, {
    hideLoading: true,
    jsonSampleExpandLevel: 3,
    expandResponses: "200,201",
}, document.querySelector("redoc"), () => {
    const toctree = document.querySelector('#toctree li.toctree-l2.current');
    if (!toctree) return;

    const apiContent = document.querySelector('#redoc .api-content');
    if (!apiContent) return;

    // Get all direct child divs and find ones with single-slash IDs (tag headings rather than endpoints)
    const tags = Array.from(apiContent.children)
        .filter(el => el.tagName === 'DIV' && el.id && (el.id.match(/\//g) || []).length === 1);
    if (tags.length === 0) return;

    const ul = document.createElement('ul');
    tags.forEach(tag => {
        const h2 = tag.querySelector('h2');
        const title = h2 ? h2.textContent.trim() : tag.id;
        const li = document.createElement('li');
        li.className = 'toctree-l3';
        const a = document.createElement('a');
        a.className = 'reference internal';
        a.href = '#' + tag.id;
        a.textContent = title.replace(/-/g, ' ').charAt(0).toUpperCase() + title.replace(/-/g, ' ').slice(1);
        h2.textContent = a.textContent
        li.appendChild(a);
        ul.appendChild(li);
    });

    // Insert the container after the current toctree item
    toctree.appendChild(ul);
});
