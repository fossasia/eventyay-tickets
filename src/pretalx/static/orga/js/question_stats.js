nv.addGraph(() => {
  try {
    const data = JSON.parse(
      document.getElementById("question-data").dataset.states
    )
    let chart = nv.models
      .pieChart()
      .x(d => d.answer || d.options__answer)
      .y(d => d.count)
      .valueFormat(d3.format("d"))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    d3.select("#question-answers svg")
      .datum(data)
      .call(chart)
    nv.utils.windowResize(() => {
      chart.update()
    }) //Update the chart when window resizes.
    chart.update()
    return chart
  } catch {}
})
