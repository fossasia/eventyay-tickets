$(document).ready(function () {
  // Initialize typeahead for event search
  var eventSearch = new Bloodhound({
    datumTokenizer: Bloodhound.tokenizers.obj.whitespace("name"),
    queryTokenizer: Bloodhound.tokenizers.whitespace,
    remote: {
      url: "/common/events/search/?query=%QUERY",
      wildcard: "%QUERY",
    },
  });

  $("#dashboard_query").typeahead(
    {
      hint: true,
      highlight: true,
      minLength: 1,
    },
    {
      name: "events",
      display: "name",
      source: eventSearch,
      templates: {
        suggestion: function (data) {
          return `<div><a href="/common/event/${data.organizer}/${data.slug}/">${data.name}</a></div>`;
        },
      },
    }
  );
});
