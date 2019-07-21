document.addEventListener("DOMContentLoaded", function() {
  if ($(".colorpickerfield").length) {
    $(".colorpickerfield")
      .parent()
      .colorpicker({
        format: "hex",
        align: "left",
        autoInputFallback: false,
        customClass: "colorpicker-2x",
        sliders: {
          saturation: {
            maxLeft: 200,
            maxTop: 200,
          },
          hue: {
            maxTop: 200,
          },
          alpha: {
            maxTop: 200,
          },
        },
      })
      .on("colorpickerChange", function(e) {
        var rgb = $(this)
          .colorpicker("color")
          ._color.rgb()
        var c = contrast([255, 255, 255], [rgb.red(), rgb.green(), rgb.blue()])
        var mark = "times"
        if (
          $(this)
            .parent()
            .find(".contrast-state").length === 0
        ) {
          $(this)
            .parent()
            .append("<div class='help-block contrast-state'></div>")
        }
        let goal = null
        if (
          $(this)
            .parent()
            .find(".color-visible")
        ) {
          goal = "visible"
        } else {
          goal = "readable"
        }
        var $note = $(this)
          .parent()
          .find(".contrast-state")
        if (goal === "readable") {
          if (c > 7) {
            $note
              .html("<span class='fa fa-fw fa-check-circle'></span>")
              .append("Your color has great contrast and is very easy to read!")
            $note
              .addClass("text-success")
              .removeClass("text-warning")
              .removeClass("text-danger")
          } else if (c > 2.5) {
            $note
              .html("<span class='fa fa-fw fa-info-circle'></span>")
              .append(
                "Your color has decent contrast and is probably good-enough to read!"
              )
            $note
              .removeClass("text-success")
              .removeClass("text-warning")
              .removeClass("text-danger")
          } else {
            $note
              .html("<span class='fa fa-fw fa-warning'></span>")
              .append(
                "Your color has bad contrast for text on white background, please choose a darker " +
                  "shade."
              )
            $note
              .addClass("text-danger")
              .removeClass("text-success")
              .removeClass("text-warning")
          }
        } else {
          if (c > 7) {
            $note
              .html("<span class='fa fa-fw fa-check-circle'></span>")
              .append("Your color has great contrast and is very easy to see!")
            $note
              .addClass("text-success")
              .removeClass("text-warning")
              .removeClass("text-danger")
          } else if (c > 2.5) {
            $note
              .html("<span class='fa fa-fw fa-info-circle'></span>")
              .append("Your color has decent contrast and is good to see!")
            $note
              .removeClass("text-success")
              .removeClass("text-warning")
              .removeClass("text-danger")
          } else {
            $note
              .html("<span class='fa fa-fw fa-warning'></span>")
              .append(
                "Your color has bad contrast and will be hard to spot or differentiate."
              )
            $note
              .addClass("text-danger")
              .removeClass("text-success")
              .removeClass("text-warning")
          }
        }
      })
  }
})

function luminanace(r, g, b) {
  var a = [r, g, b].map(function(v) {
    v /= 255
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
  })
  return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722
}
function contrast(rgb1, rgb2) {
  var l1 = luminanace(rgb1[0], rgb1[1], rgb1[2]) + 0.05,
    l2 = luminanace(rgb2[0], rgb2[1], rgb2[2]) + 0.05,
    ratio = l1 / l2
  if (l2 > l1) {
    ratio = 1 / ratio
  }
  return ratio.toFixed(1)
}
