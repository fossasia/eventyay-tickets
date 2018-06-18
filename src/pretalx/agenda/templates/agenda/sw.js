var cacheName = 'orgaScheduleCache';

self.addEventListener('fetch', function(event) {
  event.respondWith(
    fetch(event.request)
      .then(function (response) {
        // if request is successful, save it in cache
        var responseToCache = response.clone();

        caches.open(cacheName).then(function (cache) {
          cache.put(event.request, responseToCache);
        });

        return response;
      })
      .catch(function () {
        // if request failed, serve the content from cache
        return fromCache(event.request);
      })
  )
});

function fromCache(request) {
  return caches.open(cacheName).then(function (cache) {
    return cache.match(request).then(function (matching) {
      return matching;
    })
  });
}