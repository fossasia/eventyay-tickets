// start when DOM is ready

const removeLightbox = () => {
    const lightboxWrapper = document.querySelector('.lightbox-wrapper')
    if (lightboxWrapper) {
        lightboxWrapper.parentNode.removeChild(lightboxWrapper)
    }
}

const buildLightbox = (url) => {
    const lightboxWrapper = document.createElement('div')
    lightboxWrapper.className = 'lightbox-wrapper'

    const lightbox = document.createElement('div')
    lightbox.className = 'lightbox'
    lightboxWrapper.appendChild(lightbox)
    lightbox.addEventListener('click', (event) => {
        event.stopPropagation()
    })
    // put image into lightbox with link to original image
    lightbox.innerHTML = `
        <a href="${url}" target="_blank">
          <img src="${url}" />
        </a>
        <div class="lightbox-close"><i class="fa fa-times"></i></div>
    `
    document.body.appendChild(lightboxWrapper)
    lightboxWrapper.addEventListener('click', removeLightbox)
    document.querySelector('.lightbox-close').addEventListener('click', removeLightbox)
}

const setupLightbox = () => {
    // work with images or links with attribute data-lightbox

    if (document.querySelectorAll('a[data-lightbox], img[data-lightbox]').length) {
        window.addEventListener('keyup', (event) => {
            if (event.key === 'Escape') {
                removeLightbox()
            }
        })
        document.querySelectorAll('a[data-lightbox], img[data-lightbox]').forEach((element) => {
            element.addEventListener("click", function(event) {
                removeLightbox()  // just to be safe
                const imageUrl = element.dataset.lightbox || element.src || element.href
                if (!imageUrl) {
                    return;
                }
                event.preventDefault()
                buildLightbox(imageUrl)
            })
        })
    }
}
document.addEventListener("DOMContentLoaded", setupLightbox)
if (document.readyState === 'complete' || document.readyState === 'loaded') {
    setupLightbox()
}
