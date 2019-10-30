/* PRETALX SCHEDULE WIDGET BEGINS HERE */

Vue.component('pretalx-schedule-talk', {
    template: `
        <a
            :class="['pretalx-schedule-talk', isActive ? 'active': '']"
            :id="'pretalx-' + talk.code"
            :title="talk.title + '(' + talk.display_speaker_names + ')'"
            :style="style"
            :data-time="timeDisplay"
            :data-start="talk.start"
            :data-end="talk.end"
            target="_blank"
            rel="noopener"
            :href="data.event + 'talk/' + talk.code"
        >
            <div class="pretalx-schedule-talk-content">
                <span v-if="talk.do_not_record" class="fa-stack">
                    <i class="fa fa-video-camera fa-stack-1x"></i>
                    <i class="fa fa-ban do-not-record fa-stack-2x" aria-hidden="true"></i>
                </span>
                <span class="pretalx-schedule-talk-title">{{ talk.title }}</span>
                <span class="pretalx-schedule-talk-speakers" v-if="talk.display_speaker_names">({{ talk.display_speaker_names }})</span><br>
            </div>
        </a>
    `,
    props: {
        talk: Object,
        track: Object,
        data: Object,
    },
    computed: {
        style() {
            return {
                height: this.talk.height + "px",
                "top": this.talk.top + "px",
                "min-height": (this.talk.height >= 30 ? this.talk.height : 30) + "px",
                "border-color": this.talk.track.color || "inherit",
                "cursor": "pointer",
            }
        },
        isActive () {
            const now = moment()
            return moment(this.talk.start) > now && moment(this.talk.end) < now
        },
        timeDisplay () {
            return moment(this.talk.start).format("LT") + ' - ' + moment(this.talk.end).format("LT")
        }
    },
});
Vue.component('pretalx-schedule-room', {
    template: `
        <div class="pretalx-schedule-room">
            <div class="pretalx-schedule-talk-container" :style="style">
                <pretalx-schedule-talk :talk="talk" v-for="talk in room.talks" :key="talk.code" :data="data">
                </pretalx-schedule-talk>
            </div>
        </div>
    `,
    props: {
        height: Number,
        room: Object,
        data: Object,
    },
    computed: {
        style () {
            return {
                height: this.height + "px"
            }
        }
    }
});
Vue.component('pretalx-schedule-day', {
    template: `
        <section class="pretalx-schedule-day-wrapper" :style="style">
            <div class="pretalx-schedule-day" :data-start="day.display_start">
                <div class="pretalx-schedule-day-header-row">
                    <span class="pretalx-schedule-time-column pretalx-schedule-day-header"></span>
                    <div class="pretalx-schedule-day-room-header" v-for="room in day.rooms" :key="room.name">
                        {{ room.name }}
                    </div>
                </div>
                <div class="pretalx-schedule-rooms">
                    <div class="pretalx-schedule-nowline" :style="nowlineStyle"></div>
                    <div class="pretalx-schedule-time-column">
                        <div class="pretalx-schedule-hour" v-for="hour in day.hours">{{ hour }}</div>
                    </div>
                    <pretalx-schedule-room v-for="room in day.rooms" :room="room" :key="room.name" :data="data"></pretalx-schedule-room>
                </div>
            </div>
        </section>
    `,
    props: {
        day: Object,
        data: Object,
    },
    computed: {
        style () {
            if (this.data.height) {
                return {
                    "max-height": "calc(" + this.data.height + " - 50px)",
                }
            }
        },
        nowlineStyle () {
            const now = moment()
            const start = moment(this.day.display_start)
            const end = moment(this.day.end)
            if ((now < end) && (now > start)) {
                const diff_seconds = now.diff(start, "seconds")
                const diff_px = (diff_seconds / 60 / 60) * 120
                return {"top": diff_px + "px", "visibility": "visisble"}
            }
        },
    }
});

Vue.component('pretalx-schedule-widget', {
    template: `
    <div :class="['pretalx-schedule-wrapper', mobile ? 'mobile' : '']" ref="wrapper" :style="style">
        <div class="pretalx-tabs" v-if="scheduleData && scheduleData.schedule && scheduleData.schedule.length > 1">
            <div class="pretalx-tab" v-for="day in scheduleData.schedule" :class="[currentDay === day.start ? 'active' : '',]" @click="currentDay = day.start">
              <label class="pretalx-tab-label">
                  {{ day.start|dateDisplay }}
              </label>
            </div>
        </div>
        <template v-if="scheduleData && scheduleData.schedule">
            <pretalx-schedule-day v-for="day in scheduleData.schedule" :day="day" :key="day.start" v-if="day.start==currentDay" :data="widgetData">
            </pretalx-schedule-day>
        </template>
        <div v-else>
            <i class="fa fa-spinner fa-pulse fa-4x fa-fw text-primary mb-4 mt-4"></i>
        </div>
        <div class="pretix-widget-attribution" style="text-align: center">
            · powered by <a href="https://pretalx.com" rel="noopener" target="_blank">pretalx</a> ·
        </div>
    </div>`,
    data: function () {
        return {
            scheduleData: null,
            widgetData: null,
            loading: true,
            mobile: false,
            currentDay: null,
        }
    },
    created: function () {
        moment.locale(lang)
        moment.updateLocale(lang, {
            longDateFormat: {
                LL: moment.localeData()._longDateFormat.LL.replace(/Y/g, '').replace(/,? *$/, ''),
            }
        });
        this.widgetData = widgetData;
        fetch(this.widgetData.event + "schedule/widget/v1.json").then((response) => {
            response.json().then((data) => {
                this.scheduleData = data;
                this.loading = false;
                this.currentDay = data.schedule[0].start
            })
        })
    },
    mounted: () => {
        this.mobile = this.$refs && this.$refs.wrapper && this.$refs.wrapper.clientWidth <= 800;
    },
    computed: {
        style () {
            if (this.widgetData.height) {
                return {
                    "max-height": this.widgetData.height,
                    display: "block",
                }
            }
        },
    },
    filters: {
        dateDisplay: (value) => {
            return moment(value).format("dddd, LL")
        }
    }
});

/* Function to create the actual Vue instances */

let widgetData = {}
const create_widget = () => {
    let element = document.querySelector("pretalx-schedule-widget")
    if (!element) {
        element = document.querySelector(".pretalx-schedule-widget-compat")
    }
    for (var i = 0; i < element.attributes.length; i++) {
        var attrib = element.attributes[i];
        if (attrib.name.match(/^data-.*$/)) {
            widgetData[attrib.name.replace(/^data-/, '')] = attrib.value;
        } else {
            widgetData[attrib.name] = attrib.value;
        }
    }
    if (!widgetData.event.match(/\/$/)) {
        widgetData.event += "/";
    }

    var app = new Vue({el: "pretalx-schedule-widget"});
    return app;
};

function docReady(fn) {
    // see if DOM is already available
    if (document.readyState === "complete" || document.readyState === "interactive") {
        // call on next available tick
        setTimeout(fn, 1);
    } else {
        document.addEventListener("DOMContentLoaded", fn);
    }
}

docReady(create_widget)
