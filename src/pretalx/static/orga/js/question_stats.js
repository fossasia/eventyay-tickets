const serverData = document.getElementById("question-data")
const canvas = document.getElementById("question-answers")
const data = JSON.parse(serverData.dataset.states)
let url = serverData.dataset.url
const options = {
  series: data.map(e => e.count),
  labels: data.map(e => e.answer || e.options__answer),
  chart: {
    width: 420,
    type: 'donut',
    events: {
      dataPointSelection: (event, chartContext, config) => {
        const clickedData = data[config.dataPointIndex]
        if (clickedData.answer) {
          url = url + "answer=" + encodeURIComponent(clickedData.answer)
        } else {
          url = url + "answer__options=" + encodeURIComponent(clickedData.options)
        }
        window.location.href = url
      },
      dataPointMouseEnter: () => {
        canvas.style.cursor = "pointer"
      },
      dataPointMouseLeave: () => {
        canvas.style.cursor = "inherit"
      },
    },
  },
  dataLabels: {
    enabled: false
  },
  fill: {
    type: 'gradient',
  },
  legend: {
    formatter: function(val, opts) {
      return val + " - " + opts.w.globals.series[opts.seriesIndex]
    }
  },
  responsive: [{
    breakpoint: 480,
    options: {
      chart: {
        width: 200
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
          show: true
        }
      }
    }
  },
  tooltip: {
    enabled: false
  }
};

let chart = new ApexCharts(document.querySelector("#question-answers"), options);
chart.render();
