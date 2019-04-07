nv.addGraph(() => {
  try {
    const data = JSON.parse(document.getElementById('timeline-data').dataset.timeline).map((element) => { return {x: new Date(element.x), y: element.y} });
    const yMax = Math.max(...data.map((e) => {return e.y})) + 1;
    let chart = nv.models.lineChart()
                  .margin({left: 100, right: 100})
                  .useInteractiveGuideline(true)
                  .showLegend(false)
                  .showYAxis(true)
                  .showXAxis(true)
                  .forceY([0, yMax])
    ;

    chart.xAxis     //Chart x-axis settings
        .axisLabel('Time')
        .tickFormat((d) => {
          return d3.time.format('%x')(new Date(d))
        })
    ;
    chart.yAxis     //Chart y-axis settings
        .axisLabel('Submissions')
        .tickFormat(d3.format('d'))
    ;
    d3.select('#submission-stats svg')
        .datum([{values: data, color: '#3aa57c', key: 'Submissions', area: true, strokeWidth: 2}])
        .call(chart)
    ;
    nv.utils.windowResize(() => { chart.update() }); //Update the chart when window resizes.
    return chart;
  } catch {}
});

nv.addGraph(() => {
  try {
    const data = JSON.parse(document.getElementById('state-data').dataset.states)
    let chart = nv.models.pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format('d'))
      .legendPosition("right")
      .showLabels(false)
    ;
    d3.select('#submission-states svg').datum(data).call(chart);
    return chart
  } catch {}
});

nv.addGraph(() => {
  try {
    const data = JSON.parse(document.getElementById('type-data').dataset.states)
    let chart = nv.models.pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format('d'))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    ;
    d3.select('#submission-types svg').datum(data).call(chart);
    return chart
  } catch {}
});

nv.addGraph(() => {
  try {
    const data = JSON.parse(document.getElementById('track-data').dataset.states)
    let chart = nv.models.pieChart()
      .x(d => d.label)
      .y(d => d.value)
      .valueFormat(d3.format('d'))
      .labelsOutside(true)
      .legendPosition("right")
      .showLabels(false)
    ;
    d3.select('#submission-tracks svg').datum(data).call(chart);
    return chart
  } catch {

  }
});
