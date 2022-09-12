var api = {
  cache: {},
  http(verb, url, body) {
    var fullHeaders = {}
    fullHeaders["Content-Type"] = "application/json"
    fullHeaders["X-CSRFToken"] = getCookie("pretalx_csrftoken")

    let options = {
      method: verb || "GET",
      headers: fullHeaders,
      credentials: "include",
      body: body && JSON.stringify(body),
    }
    return window
      .fetch(url, options)
      .then(response => {
        if (response.status === 204) {
          return Promise.resolve()
        }
        return response.json().then(json => {
          if (!response.ok) {
            return Promise.reject({ response, json })
          }
          return Promise.resolve(json)
        })
      })
      .catch(error => {
        return Promise.reject(error)
      })
  },
  fetchTalks(options) {
    options = options || {}
    var url = [
      window.location.protocol,
      "//",
      window.location.host,
      window.location.pathname,
      "api/talks/",
    ].join("")
    if (window.location.search) {
      url += window.location.search + "&"
    } else {
      url += "?"
    }
    if (options.since) {
      url += `since=${encodeURIComponent(options.since)}&`
    }
    if (options.warnings) {
      url += 'warnings=true'
    }
    return api.http("GET", url, null)
  },
  fetchRooms(eventSlug) {
    const url = [
      window.location.protocol,
      "//",
      window.location.host,
      "/api/events/",
      eventSlug,
      "/rooms",
    ].join("")
    return api.http("GET", url, null)
  },
  fetchAvailabilities(talkid, roomid, check_cache = true) {
    var url = [
      window.location.protocol,
      "//",
      window.location.host,
      window.location.pathname,
      "api/availabilities/",
      talkid,
      "/",
      roomid,
      "/",
      window.location.search,
    ].join("")

    if (check_cache && api.cache[url]) {
      return api.cache[url]
    } else {
      api.cache[url] = api.http("GET", url, null)
    }

    return api.cache[url]
  },
  saveTalk(talk) {
    var url = [
      window.location.protocol,
      "//",
      window.location.host,
      window.location.pathname,
      "api/talks/",
      talk.id ? (talk.id + "/") : "",
      window.location.search,
    ].join("")
    const action = talk.action || "PATCH"
    return api.http(action, url, {
      room: (talk.room && talk.room.id) ? talk.room.id : talk.room,
      start: talk.start,
      action: talk.action,
      duration: talk.duration,
      description: talk.description,
    })
  },
  deleteTalk(talk) {
    return api.saveTalk({id: talk.id, action: "DELETE"})
  },
  createTalk(talk) {
    talk.action = "POST"
    return api.saveTalk(talk)
  }
}

var dragController = {
  draggedTalk: null,
  modalTalk: null,

  event: null,
  roomColumn: null,
  dragPosX: null,
  dragPosY: null,
  startY: null,
  dragSource: null,
  isCreating: false,

  startDraggingTalk(talk, dragSource, dragPosX, dragPosY) {
    this.draggedTalk = JSON.parse(JSON.stringify(talk))
    this.dragPosX = dragPosX
    this.dragSource = dragSource
    this.dragPosY = dragPosY
    this.dragSource.classList.add("drag-source")
  },
  stopDragging() {
    if (this.roomColumn) {
      this.roomColumn.classList.remove("hover-active")
    }
    this.dragSource.classList.remove("drag-source")
    this.draggedTalk = null
    this.event = null
    this.startY = null
  },
  startModal(talk) {
    this.modalTalk = talk
    this.draggedTalk = null
    this.stopDragging()
  },
  switchToModal() {
    this.modalTalk = this.draggedTalk
    this.draggedTalk = null
    this.stopDragging()
  },
  closeModal() {
    this.modalTalk = null;
  }
}

function generateTimesteps(start, interval, intervalunit, end) {
  var steps = [],
    d = moment(start)

  while (d < end) {
    steps.push(moment(d))
    d.add(interval, intervalunit)
  }

  return steps
}

Vue.component("availability", {
  template: `
    <div class="room-availability" v-bind:style="style"></div>
  `,
  props: {
    availability: Object,
    start: Object,
  },
  computed: {
    duration() {
      if (this.availability.end) {
        return moment(this.availability.end).diff(
          this.availability.start,
          "minutes"
        )
      } else {
        return 60 * 24
      }
    },
    style() {
      var style = { height: this.duration + "px" }
      style.transform =
        "translatey(" +
        moment(this.availability.start).diff(this.start, "minutes") +
        "px)"
      return style
    },
  },
})

Vue.component("modal", {
  template: `
    <div id="schedule-modal" class="schedule-modal">
      <h2 v-if="talk.id">Edit break</h2>
      <h2 v-else>New break</h2>
      <form class="form-control">
        <div class="form-group row">
          <label class="col-md-3 col-form-label">Description</label>
          <div class="col-md-9"><div class="i18n-form-group">
            <input type="text" class="form-control" :title="locale" :lang="locale" v-model="talk.description[locale]" v-for="locale in locales" v-on:keyup.enter="saveTalk">
          </div></div>
        </div>
        <div class="form-group row">
          <label class="col-md-3 col-form-label">Duration</label>
          <div class="col-md-9"><div class="input-group">
            <input type="number" name="duration" value="30" min="5" class="form-control" placeholder="Duration" title="Duration in minutes" v-model="talk.duration" v-on:keyup.enter="saveTalk">
            <div class="input-group-append"><span class="input-group-append input-group-text">minutes</span></div>
          </div>
        </div></div>
        <div class="button-row">
          <div class="btn btn-outline-danger" @click="deleteTalk" v-if="talk.id">Delete</div>
          <div v-else></div>
          <div class="btn btn-success" @click="saveTalk">Save</div>
        </div>
      </form>
    </div>
  `,
  props: {
    talk: Object,
    locales: Array,
  },
  created () {
    if (!this.talk.description) {
      this.talk.description = {"en": ""}
    }
    if (!this.talk.duration && this.talk.start) {
      this.talk.duration = moment(this.talk.end).diff(this.talk.start, "minutes")
    }
  },
  methods: {
    deleteTalk () {
      api.deleteTalk(this.talk).then((resp) => {
        this.$emit("deleteTalk", this.talk)
        dragController.closeModal()
      })
    },
    saveTalk () {
      if (this.talk.id) {
        this.talk.end = moment(this.talk.start).add(this.talk.duration, "minutes")
        api.saveTalk(this.talk).then(resp => {
          dragController.closeModal()
          this.talk.duration = resp.duration
          this.talk.start = resp.start
          this.talk.end = resp.end
          this.$emit("saveTalk", this.talk)
        })
      } else {
        if (this.talk.duration) {
          api.createTalk(this.talk).then(resp => {
            dragController.closeModal()
            this.$emit("newTalk", resp)
          })
        }
      }
    },
  }
})

Vue.component("talk", {
  template: `
    <div class="talk-box" :class="[talk.state, {dragged: isDragged, warning: displayWarnings, break: isBreak}]" v-bind:style="style" @mousedown="onMouseDown"
         :title="title" :data-original-title="title" data-toggle="tooltip">
      <span v-if="displayWarnings" class="warning-sign"><i class="fa fa-warning"></i></span>
      <span v-if="(!isDragged || !this.talk.start) && talk.title">{{ talk.title }}</span>
      <span v-if="isBreak && !isDragged" class="description">{{ breakDescription }}</span>
      <span class="time" v-if="this.talk.start && this.isDragged && this.talk.id">
        <span>{{ humanStart }}</span>
      </span>
      <span class="time" v-else-if="this.isDragged">
        <span>{{ talk.duration }} minutes</span>
      </span>
    </div>
  `,
  props: {
    talk: Object,
    start: Object,
    isDragged: { type: Boolean, default: false },
  },
  computed: {
    title() {
      let title = this.start ? this.humanStart : ""
      title += " (" + this.talk.duration + " minutes)"
      if (this.displayWarnings) {
        title = title + "\n\n" + this.displayWarnings
      }
      if (this.talk.state === "accepted") {
        title = title + "\n Not confirmed yet!"
      }
      return title
    },
    breakDescription () {
      if (!this.talk.description) return ""
      if (this.talk.description.en) return this.talk.description.en
      return this.talk.description.values ? this.talk.description.values[0] : ""
    },
    style() {
      var style = { height: this.talk.duration + "px" }
      if (this.talk.track && this.talk.track.color) {
        style.borderColor = this.talk.track.color
      }
      style.transform =
        "translateY(" +
        moment(this.talk.start).diff(this.start, "minutes") +
        "px)"
      return style
    },
    humanStart() {
      return moment.tz(this.talk.start, app.timezone).format("HH:mm")
    },
    displayWarnings() {
      return this.talk.warnings
        ? this.talk.warnings.map(warning => warning.message).join("\n")
        : null
    },
    isBreak() {
      return !this.talk.submission_type
    },
  },
  methods: {
    onMouseDown(event) {
      if (event.buttons === 1) {
        var talkRect = this.$el.getBoundingClientRect()
        dragController.isCreating = false
        dragController.startDraggingTalk(
          this.talk,
          this.$el,
          event.clientX - talkRect.left,
          event.clientY - talkRect.top
        )
      }
    },
  },
})

Vue.component("timestep", {
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
    style() {
      if (!this.thin) return {}
      var style = { position: "absolute", top: 0 }
      style.transform =
        "translatey(" +
        moment(this.timestep).diff(this.start, "minutes") +
        "px)"
      return style
    },
    isMidnight() {
      return (
        (this.timestep.hour() === 0 && this.timestep.minute() === 0) &
        !this.thin
      )
    },
  },
})

Vue.component("room", {
  template: `
    <div class="room-column">
      <a v-bind:href="room.url" :title="displayName"><div class="room-header">{{ displayName }}</div></a>
      <div class="room-container" v-bind:style="style" :data-id="room.id" @mousedown="onMouseDown">
      <availability v-for="avail in availabilities" :availability="avail" :start="start" :key="avail.id"></availability>
      <talk ref="draggedTalk"
          v-if="dragController.draggedTalk && dragController.event && dragController.draggedTalk.room == this.room.id" :talk="dragController.draggedTalk" :key="dragController.draggedTalk.id" :is-dragged="true" :start="start">
      </talk>
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
    availabilities() {
      if (dragController.draggedTalk && dragController.draggedTalk.id) {
        return api
          .fetchAvailabilities(dragController.draggedTalk.id, this.room.id)
          .then(result => result.results)
      } else {
        return this.room.availabilities
      }
    },
  },
  computed: {
    myTalks() {
      return (this.talks || []).filter(element => element.room === this.room.id)
    },
    midnights() {
      return generateTimesteps(this.start, 24, "h", this.end).slice(1)
    },
    displayName() {
      return Object.values(this.room.name)[0]
    },
    style() {
      return {
        height: this.duration + "px",
      }
    },
    dragController () { return dragController }
  },
  methods: {
    onMouseDown(event) {
      if (event.buttons === 1 && !dragController.draggedTalk) {
        var talkRect = this.$el.getBoundingClientRect()
        dragController.isCreating = true
        dragController.startDraggingTalk(
          {start: null, end: null, room: this.room, duration: null, description: null},
          this.$el,
          event.clientX - talkRect.left,
          0
        )
      }
    }
  }
})

var app = new Vue({
  el: "#fahrplan",
  template: `
    <div @mousemove="onMouseMove" @mouseup="onMouseUp">
      <div id="fahrplan" :class="showUnassigned ? 'narrow' : 'wide'">
        <modal ref="modalTalk" v-if="dragController.modalTalk && dragController.modalTalk.duration" :talk="dragController.modalTalk" v-on:deleteTalk="deleteTalk" v-on:saveTalk="saveTalk" :locales="locales" v-on:newTalk="newTalk"></modal>
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
          <room v-for="room in filteredRooms" :room="room" :talks="talks" :duration="duration" :start="start" :end="end" :key="room.id">
          </room>
        </div>
      </div>
      <div id="unassigned-group">
        <div class="talk-header" ref="roomHeader" @click="showUnassigned = !showUnassigned" :class="showUnassigned ? 'present': 'collapsed'">Unassigned Talks</div>
        <div id='unassigned-talks' v-if="showUnassigned">
          <div class="input-group">
            <div class="input-group-prepend input-group-text"><i class="fa fa-search"></i></div>
            <input type="text" class="form-control" placeholder="title track:foo type:baz" v-model="search">
          </div>
          <div id="unassigned-container" ref="unassigned">
              <talk v-for="talk in filteredTalks" v-if="!talk.room" :talk="talk" :key="talk.id"></talk>
          </div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      talks: null,
      rooms: null,
      start: null,
      end: null,
      since: null,
      timezone: null,
      locales: null,
      loading: true,
      showUnassigned: true,
      search: "",
      dragController: dragController,
      selectedRooms: [],
    }
  },
  created() {
    $("#id_version").on("change", e => {
      document.querySelector("#schedule-version").submit()
    })
    $("#id_room").on("change", e => {
      this.updateRooms()
    })
    api.fetchRooms(this.eventSlug).then(result => {
      this.rooms = result.results
    })
    api
      .fetchTalks()
      .then(result => {
        this.talks = result.results.sort((a, b) => (a.title < b.title) ? -1 : 1)
        this.timezone = result.timezone
        this.start = moment.tz(result.start, this.timezone)
        this.end = moment.tz(result.end, this.timezone)
        this.locales = result.locales
        this.since = result.now
      })
      .then(() => this.updateRooms())
      .then(() => {
        this.loading = false
        $(function() {
          $('[data-toggle="tooltip"]').tooltip()
        })
      })
      .then(() => {
        // load warnings later, because they are slow
        api.fetchTalks({warnings: true}).then(result => {
          this.talks = result.results.sort((a, b) => (a.title < b.title) ? -1 : 1)
          this.since = result.now
        })
      })
    window.setTimeout(this.pollUpdates, 10*1000)
  },
  computed: {
    currentDay() {},
    duration() {
      return this.end ? this.end.diff(this.start, "minutes") : null
    },
    timesteps() {
      return generateTimesteps(this.start, 30, "m", this.end)
    },
    filteredTalks() {
      if (!this.talks) return []
      const searchTerms = this.search
          .split(" ")
          .filter(d => d.length)
          .map(d => d.toLowerCase().trim())

      if (!searchTerms.length) return this.talks

      return this.talks.filter(talk => {
        const speakers = talk.speakers || []
        const title = talk.title.toLowerCase()
        const submissionType = talk.submission_type ? talk.submission_type.toLowerCase() : ""
        const track = talk.track ? talk.track.name.toLowerCase() : ""
        return searchTerms.some(term => {
          if (track && term.startsWith("track:")) {
            if (track.includes(term.substring(6))) return true
          } else if (term.startsWith("type:")) {
            if (submissionType.includes(term.substring(5))) return true
          } else {
            if (title.includes(term) || speakers.some(speaker => speaker.name.toLowerCase().includes(term))) {
              return true
            }
          }
          return false
        })
      })
    },
    filteredRooms() {
      this.updateURL();

      if (!this.rooms) return [];
      if (this.selectedRooms.length === 0) return this.rooms;

      return this.rooms.filter(room => {
        return this.selectedRooms.includes(room.id);
      })
    },
    eventSlug() {
      const relevant = window.location.pathname.substring(12)
      return relevant.substring(0, relevant.indexOf("/"))
    },
  },
  methods: {
    deleteTalk (event) {
      // only removes talk from display
      const index = this.talks.indexOf(event);
      this.talks.splice(index, 1);
    },
    newTalk(talk) {
      this.talks.push(talk)
    },
    saveTalk(response) {
      const talk = this.talks.find((talk) => talk.id == response.id)
      Object.assign(talk, response)
    },
    pollUpdates() {
      if (this.since) {
        api
          .fetchTalks({since: this.since, warnings: true})
          .then(result => {
            this.since = result.now
            result.results.forEach((data) => {
              const talk = this.talks.find((talk) => talk.id == data.id)
              Object.assign(talk, data)
            })
            window.setTimeout(this.pollUpdates, 10*1000)
          })
      }
    },
    updateURL() {
      let qp = new URLSearchParams(location.search);
      qp.delete('room');
      this.selectedRooms.forEach((r) => { qp.append('room', r) });
      history.replaceState(null, null, "?" + qp.toString());
    },
    updateRooms() {
      this.selectedRooms = [...document.querySelector("#id_room").options].filter(
        option => option.selected
      ).map(option => parseInt(option.value))
    },
    onMouseMove(event) {
      if (dragController.draggedTalk) {
        dragController.event = event
        var newRoomColumn = document.elementFromPoint(
          event.clientX,
          event.clientY
        )

        while (
          !newRoomColumn.className.match(/room-container/) &&
          newRoomColumn.id !== "unassigned-container" &&
          newRoomColumn.parentElement
        ) {
          newRoomColumn = newRoomColumn.parentElement
        }

        if (newRoomColumn.dataset.id) {
          if (newRoomColumn && newRoomColumn !== dragController.roomColumn) {
            if (dragController.roomColumn)
              dragController.roomColumn.classList.remove("hover-active")
          }
          dragController.roomColumn = newRoomColumn
          dragController.draggedTalk.room = newRoomColumn.dataset.id
          dragController.roomColumn.classList.add("hover-active")
          if (dragController.roomColumn) {
            var colRect = dragController.roomColumn.getBoundingClientRect()
            var position = event.clientY - colRect.top - (dragController.dragPosY || 0)
            position -= position % 5
            const cursorTime = moment(this.start)
              .add(position, "minutes")
              .format()
            if (dragController.isCreating) {
              if (!dragController.draggedTalk.start) {
                dragController.draggedTalk.start = cursorTime
                dragController.startY = dragController.event.clientY
              }
              dragController.draggedTalk.end = cursorTime
              dragController.draggedTalk.duration = moment(cursorTime).diff(moment(dragController.draggedTalk.start), "minutes")
            } else {
              dragController.draggedTalk.start = cursorTime
            }
          }
        } else if (newRoomColumn.id === "unassigned-container") {
          if (newRoomColumn && newRoomColumn !== dragController.roomColumn) {
            if (dragController.roomColumn)
              dragController.roomColumn.classList.remove("hover-active")
          }
          dragController.roomColumn = newRoomColumn
          dragController.draggedTalk.room = null
          dragController.draggedTalk.start = null
          dragController.roomColumn.classList.add("hover-active")
        }

        if (event.clientY < 160) {
          if (event.clientY < 110) {
            window.scrollBy({
              top: -100,
              behavior: "smooth",
            })
          } else {
            window.scrollBy({
              top: -50,
              behavior: "smooth",
            })
          }
        } else if (event.clientY > window.innerHeight - 100) {
          if (event.clientY > window.innerHeight - 40) {
            window.scrollBy({
              top: 100,
              behavior: "smooth",
            })
          } else {
            window.scrollBy({
              top: 50,
              behavior: "smooth",
            })
          }
        }
      }
    },
    onMouseUp(event) {
      if (dragController.draggedTalk && !dragController.modalTalk) {
        if (dragController.event) {
          // got dragged
          if (!dragController.draggedTalk.submission_type && !dragController.draggedTalk.room) {
            api.deleteTalk(dragController.draggedTalk).then(response => {
              this.deleteTalk(dragController.draggedTalk)
            })
          } else {
            if (!dragController.draggedTalk.id) {
              dragController.switchToModal()
            } else {
              api.saveTalk(dragController.draggedTalk).then(response => { this.saveTalk(response) })
            }
          }
        } else {
          // this is a click
          const url = dragController.draggedTalk.url
          if (url) { // this is a talk, so we open a link
            dragController.stopDragging()
            window.open(url)
          } else {
            dragController.switchToModal()
          }
        }
      } else if (dragController.modalTalk) {
          let clickElement = document.elementFromPoint(
            event.clientX,
            event.clientY
          )
          while (
            clickElement.id !== "schedule-modal" &&
            clickElement.parentElement
          ) {
            clickElement = clickElement.parentElement
          }
        if (clickElement.id !== "schedule-modal") {
          dragController.closeModal();
        }
      }
      dragController.stopDragging()
    },
  },
})
