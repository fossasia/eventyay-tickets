// Re-implement Bootstrap's collapse API in minimal vanilla JS
const collapseSelector = '[data-toggle="collapse"]';
const collapseTriggers = Array.from(document.querySelectorAll(collapseSelector));

window.addEventListener('click', (ev) => {
  const elm = ev.target.closest(collapseSelector);
  if (collapseTriggers.includes(elm)) {
    const selector = elm.getAttribute('data-target');
    collapse(selector, 'toggle');
  }
}, false);


const fnmap = {
  'toggle': 'toggle',
  'show': 'add',
  'hide': 'remove'
};
const collapse = (selector, cmd) => {
  const targets = Array.from(document.querySelectorAll(selector));
  targets.forEach(target => {
    target.classList[fnmap[cmd]]('show');
  });
}
