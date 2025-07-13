
const BASE_PATH_ID = 'base_path';
const ORGANIZER_NAME_ID = 'organizer_name';
const EVENT_SLUG_ID = 'event_slug';
const SHOW_ORGANIZER_AREA_ID = 'show_organizer_area';

$(function () {
  const basePathDefinition = document.getElementById(BASE_PATH_ID);
  const orgNameDefinition = document.getElementById(ORGANIZER_NAME_ID);
  const eventSlugDefinition = document.getElementById(EVENT_SLUG_ID);
  const showOrganizerAreaDefinition = document.getElementById(SHOW_ORGANIZER_AREA_ID);
  let basePath = '';
  if (basePathDefinition) {
    basePath = JSON.parse(basePathDefinition.textContent);
  } else {
    console.error(`JSON element to define ${BASE_PATH_ID} is missing!`)
    // This info is essential to build all items in the menu, so we can't continue without it.
    return;
  }
  let organizerName = '';
  if (orgNameDefinition) {
    organizerName = JSON.parse(orgNameDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${ORGANIZER_NAME_ID} is missing!`)
  }
  let eventSlug = '';
  if (eventSlugDefinition) {
    eventSlug = JSON.parse(eventSlugDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${EVENT_SLUG_ID} is missing!`)
  }
  let showOrganizerArea = false;
  if (showOrganizerAreaDefinition) {
    showOrganizerArea = JSON.parse(showOrganizerAreaDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${SHOW_ORGANIZER_AREA_ID} is missing!`)
  }
  const options = {
    html: true,
    content: `
      <div data-name="popover-content">
        <div class="options">
          <a href="${basePath}/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
            <i class="fa fa-ticket"></i> ${window.gettext('Tickets')}
          </a>
        </div>
        <div class="options">
          <a href="${basePath}/common/orders/" target="_self" class="btn btn-outline-success">
            <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
          </a>
        </div>
      </div>`,
    placement: 'bottom',
    trigger: 'manual'

  }
  $('[data-toggle="popover"]').popover(options).click(function (evt) {
    evt.stopPropagation();
    $(this).popover('show');
    $('[data-toggle="popover-profile"]').popover('hide');
  });
})

$(function () {
  const basePathDefinition = document.getElementById(BASE_PATH_ID);
  const orgNameDefinition = document.getElementById(ORGANIZER_NAME_ID);
  const eventSlugDefinition = document.getElementById(EVENT_SLUG_ID);
  const showOrganizerAreaDefinition = document.getElementById(SHOW_ORGANIZER_AREA_ID);
  let basePath = '';
  if (basePathDefinition) {
    basePath = JSON.parse(basePathDefinition.textContent);
  } else {
    console.error(`JSON element to define ${BASE_PATH_ID} is missing!`)
    // This info is essential to build the URL, so we can't continue without it.
    return;
  }
  let organizerName = '';
  if (orgNameDefinition) {
    organizerName = JSON.parse(orgNameDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${ORGANIZER_NAME_ID} is missing!`)
  }
  let eventSlug = '';
  if (eventSlugDefinition) {
    eventSlug = JSON.parse(eventSlugDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${EVENT_SLUG_ID} is missing!`)
  }
  let showOrganizerArea = false;
  if (showOrganizerAreaDefinition) {
    showOrganizerArea = JSON.parse(showOrganizerAreaDefinition.textContent);
  } else {
    console.warn(`JSON element to define ${SHOW_ORGANIZER_AREA_ID} is missing!`)
  }
  const currentPath = window.location.pathname;
  const queryString = window.location.search;

  const backUrl = `${currentPath}${queryString}`;

  // Constructing logout path using URLSearchParams
  const logoutParams = new URLSearchParams({ back: backUrl });
  const logoutPath = `/control/logout?${logoutParams}`;

  const profilePath = '/common/account/';
  const orderPath = '/common/orders/';

  const blocks = [
    `<div data-name="popover-profile-menu">
      <div class="profile-menu">
          <a href="${basePath}${orderPath}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-shopping-cart"></i> ${window.gettext('My Orders')}
          </a>
      </div>
      <div class="profile-menu">
          <a href="${basePath}${profilePath}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-user"></i> ${window.gettext('My Account')}
          </a>
      </div>`,
  ];

  if (showOrganizerArea) {
    blocks.push(
      `<div class="profile-menu organizer-area">
          <a href="${basePath}/control/event/${organizerName}/${eventSlug}" target="_self" class="btn btn-outline-success">
              <i class="fa fa-users"></i> ${window.gettext('Organizer Area')}
          </a>
      </div>`
    );
  }

  blocks.push(
    `<div class="profile-menu">
        <a href="${basePath}${logoutPath}" target="_self" class="btn btn-outline-success">
            <i class="fa fa-sign-out"></i> ${window.gettext('Logout')}
        </a>
    </div>`
  );

  const options = {
    html: true,
    content: blocks.join('\n'),
    placement: 'bottom',
    trigger: 'manual'
  };

  $('[data-toggle="popover-profile"]').popover(options).click(function (evt) {
    evt.stopPropagation();
    togglePopover(this);

    $(this).one('shown.bs.popover', function () {
      handleProfileMenuClick();
    });
  })
})

$('html').click(function () {
  $('[data-toggle="popover"]').popover('hide');
  $('[data-toggle="popover-profile"]').popover('hide');
});
