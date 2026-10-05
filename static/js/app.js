"use strict";
document.addEventListener("DOMContentLoaded", () => {
 const toggle = document.querySelector(".mobile-menu"), nav = document.querySelector("#navigation");
 if (toggle && nav) {
  toggle.addEventListener("click", () => {
   const expanded = toggle.getAttribute("aria-expanded") === "true";
   toggle.setAttribute("aria-expanded", String(!expanded));
   nav.classList.toggle("is-open", !expanded);
  });
  document.addEventListener("keydown", (event) => {
   if (event.key === "Escape" && nav.classList.contains("is-open")) {
    nav.classList.remove("is-open"); toggle.setAttribute("aria-expanded", "false"); toggle.focus();
   }
  });
 }
});
