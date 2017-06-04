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
    <div class="talk-box" :class="talk.state" v-bind:style="style">
      {{ talk.title }} ({{ talk.duration }} minutes)
    </div>
  `,
  props: {
    talk: Object,
    start: Object,
  },
  computed: {
    style () {
      return {
        height: this.talk.duration + 'px',
        transform: 'translatey(' + moment(this.talk.start).diff(this.start, 'minutes') + 'px)'
      }
    }
  }
})

Vue.component('room', {
  template: `
    <div class="room-column">
      <div class="room-header">{{ room.name.en }}</div>
      <div class="room-container" v-bind:style="style">
        <talk v-for="talk in myTalks" :talk="talk" :start="start" :key="talk.id"></talk>
      </div>
    </div>
  `,
  props: {
    talks: Array,
    room: Object,
    duration: Number,
    start: Object,
  },
  computed: {
    myTalks () {
      return (this.talks || []).filter((element) =>
        element.room === this.room.id
      )
    },
    style () {
      return {
        height: this.duration + 'px'
      }
    }
  }
})

var app = new Vue({
  el: '#fahrplan',
  template: `
    <div id="fahrplan">
      <div id="tracks">
        <room v-for="room in rooms" :room="room" :talks="talks" :duration="duration" :start="start" :key="room.id">
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
      talks: null,
      rooms: null,
      start: null,
      end: null,
    }
  },
  created () {
    api.fetchTalks().then((result) => {
      this.talks = result.results
    })
    api.fetchRooms().then((result) => {
      this.rooms = result.rooms
      this.start = moment(result.start)
      this.end = moment(result.end)
    })
  },
  computed: {
    currentDay () {
    },
    duration () {
      return this.end.diff(this.start, 'minutes')
    }
  }
})
