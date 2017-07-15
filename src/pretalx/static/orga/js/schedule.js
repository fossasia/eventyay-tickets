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
    return api.http('PATCH', window.location + `api/talks/${talk.id}/`, {
      room: talk.room,
      start: talk.start.format(),
    })
  }
}

var dragController = {
  draggedTalk: null,
  event: null,
  roomColumn: null,
  startDragging (talk) {
    this.draggedTalk = JSON.parse(JSON.stringify(talk))
  },
  stopDragging () {
    if (this.roomColumn) {
      this.roomColumn.classList.remove('hover-active')
      this.draggedTalk = null
      this.event = null
    }
  }
}

Vue.component('talk', {
  template: `
    <div class="talk-box" :class="[talk.state, {dragged: isDragged}]" v-bind:style="style" @mousedown="onMouseDown">
      {{ talk.title }} ({{ talk.duration }} minutes) – at {{ talk.start }}
    </div>
  `,
  props: {
    talk: Object,
    start: Object,
    isDragged: {type: Boolean, default: false},
  },
  computed: {
    style () {
      var style = {height: this.talk.duration + 'px'}
      if (this.isDragged) {
        var rect = this.$parent.$el.getBoundingClientRect()
        style.transform = 'translate(' + (dragController.event.clientX - rect.left - 50) + 'px,' + (dragController.event.clientY - rect.top - (this.talk.duration/2)) + 'px)'
      } else {
        style.transform = 'translatey(' + moment(this.talk.start).diff(this.start, 'minutes') + 'px)'
      }
      return style
    }
  },
  methods: {
    onMouseDown (event) {
      if (event.buttons === 1) {
        dragController.startDragging(this.talk)
      }
    },
  }
})

Vue.component('room', {
  template: `
    <div class="room-column">
      <div class="room-header">{{ room.name.en }}</div>
      <div class="room-container" v-bind:style="style" :data-id="room.id">
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
    <div id="fahrplan" @mousemove="onMouseMove" @mouseup="onMouseUp">
      <talk v-if="dragController.draggedTalk && dragController.event" :talk="dragController.draggedTalk" :key="dragController.draggedTalk.id" :is-dragged="true"></talk>
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
      dragController: dragController,
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
  },
  methods: {
    onMouseMove (event) {
      if (dragController.draggedTalk) {
        dragController.event = event
        var newRoomColumn = document.elementFromPoint(event.clientX, event.clientY)
        while (!newRoomColumn.dataset.id && newRoomColumn.parentElement)
          newRoomColumn = newRoomColumn.parentElement
        if (newRoomColumn.dataset.id) {
          if (newRoomColumn && (newRoomColumn !== dragController.roomColumn)) {
            if (dragController.roomColumn)
              dragController.roomColumn.classList.remove('hover-active')
            newRoomColumn.classList.add('hover-active')
            dragController.roomColumn = newRoomColumn
            dragController.draggedTalk.room = newRoomColumn.dataset.id
          }
          if (dragController.roomColumn) {
            var position = event.clientY - dragController.roomColumn.offsetTop
            position -= position % 5
            dragController.draggedTalk.start = moment(this.start).add(position, 'minutes')
          }
        }

        }
    },
    onMouseUp (event) {
      api.saveTalk(dragController.draggedTalk).then((response) => {
        this.talks.forEach((talk, index) => {
          if (talk.id == response.id) {
            Object.assign(this.talks[index], response)
          }
        })
      })
      dragController.stopDragging()
    }
  }
})
