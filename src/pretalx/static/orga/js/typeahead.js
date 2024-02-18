$(() => {
  $("#nav-search-wrapper").on(
    "shown.bs.collapse shown.bs.dropdown",
    () => $("#nav-search-dropdown input").val("").change().focus()
  )
  $("#nav-search-dropdown input").click(function(e) {
    e.stopPropagation()
  })

  $("[data-event-typeahead]").each(function() {
        console.log("got here")
    var $container = $(this)
    var $query = $(this).find("[data-typeahead-query]").length
      ? $(this).find("[data-typeahead-query]")
      : $($(this).attr("data-typeahead-field"))
    var lastQuery = null;
    var loadIndicatorTimeout = null;

    function showLoadIndicator() {
        $container.find("li").remove();
        $container.find("ul").append("<li class='loading'><span class='fa fa-4x fa-cog fa-spin'></span></li>");
        $container.toggleClass('focused', $query.is(":focus") && $container.children().length > 0);
    }

    $query.on("change", function() {
      if ($query.val() === lastQuery) {
        return
      }

      var thisQuery = $query.val()
      lastQuery = thisQuery
      window.clearTimeout(loadIndicatorTimeout)
      loadIndicatorTimeout = window.setTimeout(showLoadIndicator, 80)

      $.getJSON(
        $container.attr("data-source") + "?query=" + encodeURIComponent($query.val()) + (typeof $container.attr("data-organiser") !== "undefined" ? "&organiser=" + $container.attr("data-organiser") : ""),
        function(data) {
          if (thisQuery !== lastQuery) {
            // Ignore this response, it's for an old query
            return
          }
          window.clearTimeout(loadIndicatorTimeout);

          $container.find("li").remove()
          $.each(data.results, function(i, res) {
            let $content = $("<div>")
            if (res.type === "organiser" || res.type === "user") {
                const icon = res.type === "organiser" ? "fa-users" : "fa-user";
                $content.append(
                    $("<span>").addClass("search-title").append(
                        $("<i>").addClass("fa fa-fw " + icon)
                    ).append(" ").append($("<span>").text(res.name))
                )
            } else if (res.type === "submission" || res.type === "speaker") {
                $content.append(
                    $("<span>").addClass("search-title").append($("<span>").text(res.name))
                ).append(
                    $("<span>").addClass("search-detail").append(
                        $("<span>").addClass("fa fa-calendar fa-fw")
                    ).append(" ").append($("<div>").text(res.event).html())
                )
            } else if (res.type === "event") {
                $content.append(
                    $("<span>").addClass("search-title").append($("<span>").text(res.name))
                ).append(
                    $("<span>").addClass("search-detail").append(
                        $("<span>").addClass("fa fa-users fa-fw")
                    ).append(" ").append($("<div>").text(res.organiser).html())
                ).append(
                    $("<span>").addClass("search-detail").append(
                        $("<span>").addClass("fa fa-calendar fa-fw")
                    ).append(" ").append(res.date_range)
                )
            }

            $container.find("ul").append($("<li>")
                .append($("<a>").attr("href", res.url).append($content)
                    .on("mousedown", function(event) {
                        if ($(this).length) {
                          location.href = $(this).attr("href")
                        }
                        $(this).parent().addClass("active")
                        event.preventDefault()
                        event.stopPropagation()
                      })
                )
              )
          })
          $container.toggleClass("focused", $query.is(":focus") && $container.children().length > 0)
        }
      )
    })
    $query.on("keydown", function(event) {
      var $selected = $container.find(".active")
      if (event.which === 13) {
        // enter
        var $link = $selected.find("a")
        if ($link.length) {
          location.href = $link.attr("href")
        }
        event.preventDefault()
        event.stopPropagation()
      }
    })
    $query.on("blur", function(event) {
      $container.removeClass("focused")
    })
    $query.on("keyup", function(event) {
      var $first = $container.find("li:not(.query-holder)").first()
      var $last = $container.find("li:not(.query-holder)").last()
      var $selected = $container.find(".active")

      if (event.which === 13) {
        // enter
        event.preventDefault()
        event.stopPropagation()
        return true
      } else if (event.which === 40) {
        // down
        var $next
        if ($selected.length === 0) {
          $next = $first
        } else {
          $next = $selected.next()
        }
        if ($next.length === 0) {
          $next = $first
        }
        $selected.removeClass("active")
        $next.addClass("active")
        event.preventDefault()
        event.stopPropagation()
        return true
      } else if (event.which === 38) {
        // up
        if ($selected.length === 0) {
          $selected = $first
        }
        var $prev = $selected.prev()
        if ($prev.length === 0 || $prev.find("input").length > 0) {
          $prev = $last
        }
        $selected.removeClass("active")
        $prev.addClass("active")
        event.preventDefault()
        event.stopPropagation()
        return true
      } else {
        $(this).change()
      }
    })
  })
})
