let charts = []
nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("submission-timeline-data").dataset.timeline
    ).map(element => {
      return { x: new Date(element.x), y: element.y }
    })
    const yMax =
      Math.max(
        ...data.map(e => {
          return e.y
        })
      ) + 1
    let chart = nv.models
      .lineChart()
      .margin({ left: 100, right: 100 })
      .useInteractiveGuideline(true)
      .showLegend(false)
      .showYAxis(true)
      .showXAxis(true)
      .forceY([0, yMax])
    chart.xAxis //Chart x-axis settings
      .axisLabel("Time")
      .tickFormat(d => {
        return d3.time.format("%x")(new Date(d))
      })
    chart.yAxis //Chart y-axis settings
      .axisLabel("Submissions")
      .tickFormat(d3.format("d"))
    d3.select("#submission-timeline svg")
      .datum([
        {
          values: data,
          color: "#3aa57c",
          key: "Submissions",
          area: true,
          strokeWidth: 2,
        },
      ])
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("talk-timeline-data").dataset.timeline
    ).map(element => {
      return { x: new Date(element.x), y: element.y }
    })
    const yMax =
      Math.max(
        ...data.map(e => {
          return e.y
        })
      ) + 1
    let chart = nv.models
      .lineChart()
      .useInteractiveGuideline(true)
      .showLegend(false)
      .showYAxis(true)
      .showXAxis(true)
      .forceY([0, yMax])
    chart.xAxis //Chart x-axis settings
      .axisLabel("Time")
      .tickFormat(d => {
        return d3.time.format("%x")(new Date(d))
      })
    chart.yAxis //Chart y-axis settings
      .axisLabel("Submissions")
      .tickFormat(d3.format("d"))
    d3.select("#talk-timeline svg")
      .datum([
        {
          values: data,
          color: "#3aa57c",
          key: "Submissions",
          area: true,
          strokeWidth: 2,
        },
      ])
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("submission-state-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format("d"))
      .legendPosition("right")
      .showLabels(false)
    d3.select("#submission-states svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("talk-state-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format("d"))
      .legendPosition("right")
      .showLabels(false)
    d3.select("#talk-states svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("submission-type-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format("d"))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    d3.select("#submission-types svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("talk-type-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format("d"))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    d3.select("#talk-types svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("submission-track-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format("d"))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    d3.select("#submission-tracks svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("talk-track-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format("d"))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    d3.select("#talk-tracks svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    charts.push(chart)
    return chart
  } catch {}
})

const button = document.querySelector("#toggle-button")
button.addEventListener("click", event => {
  if (event.target.getAttribute("aria-pressed") === "true") {
    /* switch to submissions */
    const list = document.querySelectorAll(
      ".card-header.submissions, .card-body.submissions"
    )
    for (var i = 0; i < list.length; ++i) {
      list[i].classList.remove("d-none")
    }
    const list2 = document.querySelectorAll(
      ".card-header.talks, .card-body.talks"
    )
    for (var i = 0; i < list2.length; ++i) {
      list2[i].classList.add("d-none")
    }
  } else {
    /* switch to talks */
    const list = document.querySelectorAll(
      ".card-header.submissions, .card-body.submissions"
    )
    for (var i = 0; i < list.length; ++i) {
      list[i].classList.add("d-none")
    }
    const list2 = document.querySelectorAll(
      ".card-header.talks, .card-body.talks"
    )
    for (var i = 0; i < list2.length; ++i) {
      list2[i].classList.remove("d-none")
    }
  }
  for (var i = 0; i < charts.length; ++i) {
    charts[i].update()
  }
})
