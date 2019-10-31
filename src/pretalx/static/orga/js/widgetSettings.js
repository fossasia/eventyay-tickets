document.querySelector("button#generate-widget").addEventListener("click", (event) => {
  document.querySelector("#widget-generation").classList.add("d-none");
  document.querySelector("#generated-widget").classList.remove("d-none");
  const firstPre = document.querySelector("pre#widget-head");
  firstPre.innerHTML = firstPre.innerHTML.replace("LOCALE", document.querySelector("#id_locale").value);
  const secondPre = document.querySelector("pre#widget-body");
  if (document.querySelector("#id_compatibility_mode").checked) {
    secondPre.innerHTML = secondPre.innerHTML.replace("\/pretalx-schedule-widget", "/div")
    secondPre.innerHTML = secondPre.innerHTML.replace("pretalx-schedule-widget", 'div class="pretalx-schedule-widget-compat"')
  }
  const height = document.querySelector("#id_height").value || "";
  secondPre.innerHTML = secondPre.innerHTML.replace("HEIGHT", height);
})
