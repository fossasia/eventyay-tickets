document.querySelector("button#generate-widget").addEventListener("click", (event) => {
  document.querySelector("#widget-generation").classList.add("d-none");
  document.querySelector("#generated-widget").classList.remove("d-none");
  const secondPre = document.querySelector("pre#widget-body");
  secondPre.innerHTML = secondPre.innerHTML.replace("LOCALE", document.querySelector("#id_locale").value);
  secondPre.innerHTML = secondPre.innerHTML.replace("FORMAT", document.querySelector("#id_schedule_display").value);
})
