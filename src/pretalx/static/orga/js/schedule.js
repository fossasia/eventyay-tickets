var api = {
  http (verb, url, body) {
    var fullHeaders = {}
    fullHeaders['Content-Type'] = 'application/json'

    let options = {
      method: verb || 'GET',
      headers: fullHeaders,
      credentials: 'include',
      body: body && JSON.stringify(body)
    }
    return window.fetch(url, options).then((response) => {
      if (response.status === 204) {
        return Promise.resolve()
      }
      return response.json().then((json) => {
        if (!response.ok) {
          return Promise.reject({response, json})
        }
        return Promise.resolve(json)
      })
    }).catch((error) => {
      return Promise.reject(error)
    })
  },
  fetchTalks () {
    return api.http('GET', window.location + 'api/talks/', null)
  },
  fetchRooms () {
    return api.http('GET', window.location + 'api/rooms/', null)
  },
  saveTalk(talk) {
  }
}

Vue.component('talk', {
  template: `
    <div class="talk-box" :class="talk.state">
      {{ talk.title }} ({{ talk.duration }} minutes)
    </div>
  `,
  props: {
    talk: Object,
  }
})

Vue.component('room', {
  template: `
    <div class="room-column">
      <div class="room-header">{{ room.name.en }}</div>
      <talk v-for="talk in myTalks" :talk="talk" :key="talk.id"></talk>
    </div>
  `,
  props: {
    talks: Array,
    room: Object,
  },
  computed: {
    myTalks () {
      return (this.talks || []).filter((element) =>
        element.room === this.room.id
      )
    }
  }
})

var app = new Vue({
  el: '#fahrplan',
  template: `
    <div id="fahrplan">
      <div id="tracks">
        <room v-for="room in rooms" :room="room" :talks="talks" :key="room.id">
        </room>
      </div>
      <div id='unassigned-talks'>
        <div class="room-header">Unassigned Talks</div>
        <talk v-for="talk in talks" v-if="!talk.room" :talk="talk" :key="talk.id"></talk>
      </div>
    </div>
  `,
  data () {
    return {
      day: null,
      talks: null,
      rooms: null,
    }
  },
  created () {
    api.fetchTalks().then((result) => {
      this.talks = result.results
    }) 
    api.fetchRooms().then((result) => {
      this.rooms = result.results
    }) 
  },
  computed: {
    unassignedTalks () {
      return (this.talks || []).filter((element) => {
        element.room != null
      })
    },
    currentDay () {
    }
  }
})
