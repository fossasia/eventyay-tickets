const cacheName = "pretalxScheduleCache"

self.addEventListener("fetch", event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // If the request succeeded, cache response
        let responseToCache = response.clone()
        caches.open(cacheName).then(cache => {
          cache.put(event.request, responseToCache)
        })
        return response
      })
      .catch(error => {
        // If the request failed, serve the content from cache
        return fromCache(event.request)
      })
  )
})

function fromCache(request) {
  return caches.open(cacheName).then(cache => {
    return cache.match(request).then(matching => {
      return matching
    })
  })
}
