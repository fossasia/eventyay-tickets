const globalData = document.getElementById("global-data")
const dataMapping = JSON.parse(globalData.dataset.mapping)
let searchUrl = globalData.dataset.url

const drawTimeline = () => {
  const dataElements = [
    document.getElementById("submission-timeline-data"),
    document.getElementById("talk-timeline-data"),
    document.getElementById("total-submission-timeline-data"),
  ].filter(element => element.dataset.timeline)
  const element = document.getElementById("timeline")
  const deadlines = JSON.parse(globalData.dataset.annotations).deadlines.map(element => {
    return {
      x: new Date(element[0]).getTime(),
      borderColor: '#ff4560',
      strokeDashArray: 0,
      label: {
        style: {
          borderColor: '#ff4560',
          background: '#ff4560',
          color: '#fff',
          fontSize: '14px',
          padding: {top: 5}
        },
        text: element[1]
      }
    }
  })
  let options = {
    series: dataElements.map(element => {
      return {
        name: element.dataset.label,
        data: JSON.parse(element.dataset.timeline).map(element => {
          return { x: new Date(element.x), y: element.y }
        })
      }
    }),
    xaxis: {
      type: 'datetime',
      tooltip: {enabled: false},
    },
    annotations: {
      xaxis: deadlines,
    },
    chart: {
      redrawOnParentResize: true,
      height: 250,
      type: 'area',
      toolbar: {
        tools: {
          selection: false,
          zoom: false,
          zoomin: false,
          zoomout: false,
          pan: false,
          reset: false
        }
      }
    },
    colors: ["#3aa57c", "#4697c9", "#cccccc"],
    fill: {
      type: ["gradient", "gradient", "gradient"],
    },
    dataLabels: {
      enabled: false
    },
    legend: {
      formatter: function(val, opts) {
        if (val.length > 15) val = val.slice(0, 15) + "…"
        return val
      },
      position: "top"
    },
    responsive: [{
      breakpoint: 480,
      options: {
        chart: {
          width: 300,
        },
        legend: {
          position: 'bottom'
        }
      }
    }],
    tooltip: {
      enabled: true,
      shared: true,
      x: {show: true},
      marker: {show: true},
      onDatasetHover: {highlightDataSeries: true},
    }
  };
  const chart = new ApexCharts(element, options)
  chart.render()
  return chart
}

const getPieData = (id) => {
  const element = document.getElementById(id)
  if (!element.dataset.states) return
  const data = JSON.parse(element.dataset.states)
  return {
    series: data.map(e => e.value),
    labels: data.map(e => e.label),
  }
}

const drawPieChart = (data, scope, type) => {
  const id = scope + "-" + type
  const element = document.getElementById(id)
  const typeMapping = {"track": "track", "type": "submission_type", "state": "state"}
  const options = {
    series: data.series,
    labels: data.labels,
    chart: {
      width: element.clientWidth - 50,
      redrawOnParentResize: true,
      type: 'donut',
      events: {
        dataPointSelection: (event, chartContext, config) => {
          const label = config.w.config.labels[config.dataPointIndex]
          const searchValue = dataMapping[type][label]
          searchUrl += "&" + typeMapping[type] + "=" + searchValue
          window.location.href = searchUrl
        },
        dataPointMouseEnter: () => {
          element.style.cursor = "pointer"
        },
        dataPointMouseLeave: () => {
          element.style.cursor = "inherit"
        },
      },
    },
    dataLabels: {
      enabled: false
    },
    legend: {
      formatter: function(val, opts) {
        if (val.length > 15) val = val.slice(0, 15) + "…"
        return val + " - " + opts.w.globals.series[opts.seriesIndex]
      }
    },
    responsive: [{
      breakpoint: 480,
      options: {
        chart: {
          width: 300
        },
        legend: {
          position: 'bottom'
        }
      }
    }],
    plotOptions: {
      pie: {
        donut: {
          labels: {
            show: true,
            name: {
              formatter: (val) => {
                const details = val.indexOf("(")  // Truncate duration display in centre of donut chart
                if (details > -1) val = val.substring(0, details)
                if (val.length < 16) return val
                return val.slice(0, 15) + "…"
              }
            }
          }
        }
      }
    },
    tooltip: {
      enabled: false
    }
  };

  let chart = new ApexCharts(element, options);
  chart.render();
  return chart

}

let chartTypes = ["state"]
if (dataMapping.type && (Object.keys(dataMapping.type).length > 1)) chartTypes.push("type")
if (dataMapping.track) chartTypes.push("track")
let submissionChartData = chartTypes.reduce(
  (result, item, index, array) => {
    const data = getPieData("submission-" + item + "-data")
    if (data) result[item] = data
    return result
  },
  {}
)
let talkChartData = chartTypes.reduce(
  (result, item, index, array) => {
    result[item] = getPieData("talk-" + item + "-data")
    return result
  },
  {}
)
/* generate timeline data. delay to draw the correct size immediately */
setTimeout(drawTimeline, 10)

let charts = []
for (const [key, data] of Object.entries(submissionChartData)) {
  charts.push(drawPieChart(data, "submission", key))
}


const toggleButton = document.querySelector("#toggle-button")
toggleButton.addEventListener("click", event => {
  charts.forEach(chart => chart.destroy())
  charts = []
  if (event.target.getAttribute("aria-pressed") === "true") {
    /* switch to submissions */
    for (const [key, data] of Object.entries(submissionChartData)) {
      document.querySelector("#submission-" + key).classList.remove("d-none")
      document.querySelector("#talk-" + key).classList.add("d-none")
      charts.push(drawPieChart(data, "submission", key))
    }
  } else {
    /* switch to talks */
    for (const [key, data] of Object.entries(talkChartData)) {
      document.querySelector("#submission-" + key).classList.add("d-none")
      document.querySelector("#talk-" + key).classList.remove("d-none")
      charts.push(drawPieChart(data, "talk", key))
    }
  }
})
