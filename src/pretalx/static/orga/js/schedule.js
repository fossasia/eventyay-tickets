var api = {
  cache: {},
  http (verb, url, body) {
    var fullHeaders = {}
    fullHeaders['Content-Type'] = 'application/json'
    fullHeaders['X-CSRFToken'] = getCookie('pretalx_csrftoken')

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
    var url = [window.location.protocol, '//', window.location.host, window.location.pathname, 'api/talks/', window.location.search].join('')
    return api.http('GET', url, null)
  },
  fetchRooms (eventSlug) {
    const url = [window.location.protocol, '//', window.location.host, '/api/events/', eventSlug, '/rooms'].join('')
    return api.http('GET', url, null)
  },
  fetchAvailabilities (talkid, roomid, check_cache=true) {
    var url = [window.location.protocol, '//', window.location.host, window.location.pathname, 'api/availabilities/', talkid, '/', roomid, '/', window.location.search].join('')

    if (check_cache && api.cache[url]) {
      return api.cache[url];
    } else {
      api.cache[url] = api.http('GET', url, null);
    }

    return api.cache[url];
  },
  saveTalk(talk) {
    var url = [window.location.protocol, '//', window.location.host, window.location.pathname, 'api/talks/', talk.id, '/', window.location.search].join('')
    return api.http('PATCH', url, {
      room: talk.room,
      start: talk.start,
    })
  }
}

var dragController = {
  draggedTalk: null,
  event: null,
  roomColumn: null,
  dragPosX: null,
  dragPosY: null,
  dragSource: null,

  startDragging (talk, dragSource, dragPosX, dragPosY) {
    this.draggedTalk = JSON.parse(JSON.stringify(talk))
    this.dragPosX = dragPosX
    this.dragSource = dragSource
    this.dragPosY = dragPosY
    this.dragSource.classList.add('drag-source')
  },
  stopDragging () {
    if (this.roomColumn) {
      this.roomColumn.classList.remove('hover-active')
      this.dragSource.classList.remove('drag-source')
      this.draggedTalk = null
      this.event = null
    }
  }
}

function generateTimesteps(start, interval, intervalunit, end) {
  var steps = [],
      d = moment(start);

  while (d < end) {
    steps.push(moment(d));
    d.add(interval, intervalunit);
  }

  return steps;
}

Vue.component('availability', {
  template: `
    <div class="room-availability" v-bind:style="style"></div>
  `,
  props: {
    availability: Object,
    start: Object,
  },
  computed: {
    duration () {
      if(this.availability.end) {
        return moment(this.availability.end).diff(this.availability.start, 'minutes')
      } else {
        return 60 * 24
      }
    },
    style () {
      var style = {height: this.duration + 'px'}
      style.transform = 'translatey(' + moment(this.availability.start).diff(this.start, 'minutes') + 'px)'
      return style
    },
  }
})

Vue.component('talk', {
  template: `
    <div class="talk-box" :class="[talk.state, {dragged: isDragged, warning: displayWarnings}]" v-bind:style="style" @mousedown="onMouseDown"
         :title="title" data-toggle="tooltip">
      <span v-if="displayWarnings" class="warning-sign"><i class="fa fa-warning"></i></span>
      <span v-if="!isDragged || !this.talk.start">{{ talk.title }}</span>
      <span class="time" v-if="this.talk.start && this.isDragged">
        <span>{{ humanStart }}</span>
      </span>
    </div>
  `,
  props: {
    talk: Object,
    start: Object,
    isDragged: {type: Boolean, default: false},
  },
  computed: {
    title () {
      let title = this.start ? this.humanStart : '';
      title += ' (' + this.talk.duration + ' minutes)';
      if (this.displayWarnings) {
        title = title + '\n\n' + this.displayWarnings;
      }
      if (this.talk.state === 'accepted') {
        title = title + '\n Not confirmed yet!'
      }
      return title;
    },
    style () {
      var style = {height: this.talk.duration + 'px'}
      if (this.talk.track && this.talk.track.color) {
        style.borderColor = this.talk.track.color
      }
      if (this.isDragged) {
        var rect = this.$parent.$el.getBoundingClientRect()

        var colRect
        if (dragController.roomColumn) {
          colRect = dragController.roomColumn.getBoundingClientRect()
        } else {
          colRect = app.$refs.unassigned.getBoundingClientRect()
        }
        var dragTop = Math.max(colRect.top, dragController.event.clientY - dragController.dragPosY) - rect.top
        var dragLeft = dragController.event.clientX - rect.left - dragController.dragPosX

        style.transform = 'translate(' + dragLeft + 'px,' + dragTop + 'px)'
        style.width = colRect.width - 16 + 'px'
      } else if (this.talk.room !== null) {
        style.transform = 'translatey(' + moment(this.talk.start).diff(this.start, 'minutes') + 'px)'
      }
      return style
    },
    humanStart () {
      return moment.tz(this.talk.start, app.timezone).format('HH:mm')
    },
    displayWarnings () {
      return this.talk.warnings ? this.talk.warnings.map(warning => warning.message).join('\n') : null
    }

  },
  methods: {
    onMouseDown (event) {
      if (event.buttons === 1) {
        var talkRect = this.$el.getBoundingClientRect()
        dragController.startDragging(this.talk, this.$el, event.clientX - talkRect.left, event.clientY - talkRect.top)
      }
    },
  }
})

Vue.component('timestep', {
  template: `
    <div class="timestep-box" :style="style" :class="[{midnight: isMidnight, thin: thin}]">
      <span v-if="!thin">
        {{ isMidnight ? timestep.format("MM-DD") : timestep.format("HH:mm") }}
      </span>
    </div>
  `,
  props: {
    timestep: Object,
    start: Object,
    thin: Boolean,
  },
  computed: {
    style () {
      if (!this.thin) return {}
      var style = {position: "absolute", top: 0}
      style.transform = 'translatey(' + moment(this.timestep).diff(this.start, 'minutes') + 'px)'
      return style
    },
    isMidnight () {
      return (this.timestep.hour() === 0 && this.timestep.minute() === 0) & !this.thin;
    }
  },
})

Vue.component('room', {
  template: `
    <div class="room-column">
      <a v-bind:href="room.url" :title="displayName"><div class="room-header">{{ displayName }}</div></a>
      <div class="room-container" v-bind:style="style" :data-id="room.id">
      <availability v-for="avail in availabilities" :availability="avail" :start="start" :key="avail.id"></availability>
      <talk v-for="talk in myTalks" :talk="talk" :start="start" :key="talk.id"></talk>
      <timestep v-for="timestep in midnights" :timestep="timestep" :start="start" :thin="true">
      </timestep>
      </div>
    </div>
  `,
  props: {
    talks: Array,
    room: Object,
    duration: Number,
    start: Object,
    end: Object,
  },
  asyncComputed: {
    availabilities () {
      if (dragController.draggedTalk) {
        return api.fetchAvailabilities(
          dragController.draggedTalk.id,
          this.room.id,
        ).then(result => result.results);
      } else {
        return this.room.availabilities;
      }
    },
  },
  computed: {
    myTalks () {
      return (this.talks || []).filter((element) =>
        element.room === this.room.id
      )
    },
    midnights () {
      return generateTimesteps(this.start, 24, 'h', this.end).slice(1);
    },
    displayName () {
      return Object.values(this.room.name)[0]
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
    <div @mousemove="onMouseMove" @mouseup="onMouseUp">
      <div id="fahrplan" :class="showUnassigned ? 'narrow' : 'wide'">
        <talk ref="draggedTalk" v-if="dragController.draggedTalk && dragController.event" :talk="dragController.draggedTalk" :key="dragController.draggedTalk.id" :is-dragged="true"></talk>
        <div id="timeline" v-if="!loading">
          <div class="timeline-container">
            <timestep v-for="timestep in timesteps" :timestep="timestep" :start="start" :thin="false">
            </timestep>
          </div>
        </div>
        <div id="loading" v-if="loading">
            <i class="fa fa-spinner fa-pulse fa-4x fa-fw text-primary mb-4 mt-4"></i>
            <h3 class="mt-2 mb-4">Loading talks, please wait.</h3>
        </div>
        <div id="rooms" v-else>
          <div class="alert alert-danger room-column" v-if="rooms && rooms.length < 1">
            Please configure some rooms first.
          </div>
          <room v-for="room in rooms" :room="room" :talks="talks" :duration="duration" :start="start" :end="end" :key="room.id">
          </room>
        </div>
      </div>
      <div id="unassigned-group">
        <div class="talk-header" ref="roomHeader" @click="showUnassigned = !showUnassigned" :class="showUnassigned ? 'present': 'collapsed'">Unassigned Talks</div>
        <div id='unassigned-talks' v-if="showUnassigned">
          <div class="input-group">
            <div class="input-group-prepend input-group-text"><i class="fa fa-search"></i></div>
            <input type="text" class="form-control" placeholder="Search..." v-model="search">
          </div>
          <div id="unassigned-container" ref="unassigned">
              <talk v-for="talk in filteredTalks" v-if="!talk.room" :talk="talk" :key="talk.id"></talk>
          </div>
        </div>
      </div>
    </div>
  `,
  data () {
    return {
      talks: null,
      rooms: null,
      start: null,
      end: null,
      timezone: null,
      loading: true,
      showUnassigned: true,
      search: '',
      dragController: dragController,
    }
  },
  created () {
    api.fetchRooms(this.eventSlug).then((result) => {
      this.rooms = result.results
    })
    api.fetchTalks().then((result) => {
      this.talks = result.results
      this.timezone = result.timezone
      this.start = moment.tz(result.start, this.timezone)
      this.end = moment.tz(result.end, this.timezone)
    }).then(() => {
      this.loading = false
      $(function () {
        $('[data-toggle="tooltip"]').tooltip()
      })
    })
  },
  computed: {
    currentDay () {
    },
    duration () {
      return this.end ? this.end.diff(this.start, 'minutes') : null;
    },
    timesteps () {
      return generateTimesteps(this.start, 30, 'm', this.end);
    },
    filteredTalks() {
      if (!this.talks)
        return []
      return this.talks.filter(talk => {
         return talk.title.toLowerCase().indexOf(this.search.toLowerCase()) > -1
      })
    },
    eventSlug() {
      const relevant = window.location.pathname.substring(12);
      return relevant.substring(0, relevant.indexOf('/'));
    }
  },
  methods: {
    onMouseMove (event) {
      if (dragController.draggedTalk) {
        dragController.event = event
        var newRoomColumn = document.elementFromPoint(event.clientX, event.clientY)

        while (!newRoomColumn.className.match(/room-container/) && newRoomColumn.id !== "unassigned-container" && newRoomColumn.parentElement) {
          newRoomColumn = newRoomColumn.parentElement
        }

        if (newRoomColumn.dataset.id) {
          if (newRoomColumn && (newRoomColumn !== dragController.roomColumn)) {
            if (dragController.roomColumn)
              dragController.roomColumn.classList.remove('hover-active')
          }
          dragController.roomColumn = newRoomColumn
          dragController.draggedTalk.room = newRoomColumn.dataset.id
          dragController.roomColumn.classList.add('hover-active')
          if (dragController.roomColumn && app.$refs.draggedTalk) {
            var colRect = dragController.roomColumn.getBoundingClientRect()
            var dragRect = app.$refs.draggedTalk.$el.getBoundingClientRect()
            var position = dragRect.top - colRect.top
            position -= position % 5
            dragController.draggedTalk.start = moment(this.start).add(position, 'minutes').format()
          }
        } else if (newRoomColumn.id === "unassigned-container") {
          if (newRoomColumn && (newRoomColumn !== dragController.roomColumn)) {
            if (dragController.roomColumn)
              dragController.roomColumn.classList.remove('hover-active')
          }
          dragController.roomColumn = newRoomColumn
          dragController.draggedTalk.room = null
          dragController.draggedTalk.start = null
          dragController.roomColumn.classList.add('hover-active')
        }

        if (event.clientY < 160) {
          if (event.clientY < 110) {
            window.scrollBy({
              top: -100,
              behavior: 'smooth'
            });
          } else {
            window.scrollBy({
              top: -50,
              behavior: 'smooth'
            });
          }
        } else if (event.clientY > (window.innerHeight - 100)) {
          if (event.clientY > (window.innerHeight - 40)) {
            window.scrollBy({
              top: 100,
              behavior: 'smooth'
            });
          } else {
            window.scrollBy({
              top: 50,
              behavior: 'smooth'
            });
          }
        }
      }
    },
    onMouseUp (event) {
      if (dragController.draggedTalk) {
        if (dragController.event) {
          api.saveTalk(dragController.draggedTalk).then((response) => {
            this.talks.forEach((talk, index) => {
              if (talk.id == response.id) {
                Object.assign(this.talks[index], response)
              }
            })
          })
        } else {
          window.open(dragController.draggedTalk.url)
          dragController.stopDragging()
        }
      }
      dragController.stopDragging()
    }
  }
})
