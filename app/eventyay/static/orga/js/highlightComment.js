function highlightComment() {
    const fragment = window.location.hash;
    if (fragment && fragment.startsWith('#comment-')) {
        const commentId = fragment.substring(1)
        const commentElement = document.getElementById(commentId)
        if (commentElement) {
            commentElement.classList.add('card-highlight')
        }
    }
}

onReady(highlightComment)
