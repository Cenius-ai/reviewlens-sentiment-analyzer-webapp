/* Sign-in page affordances: password visibility toggle, demo credential fill and
   a submit guard so a double click cannot fire two sign-ins.
   Kept in a same-origin file so the CSP never needs inline scripts. */
(function () {
  "use strict";

  var password = document.getElementById("rl-password");
  var toggle = document.getElementById("rl-toggle-password");

  if (password && toggle) {
    toggle.addEventListener("click", function () {
      var showing = password.getAttribute("type") === "text";
      password.setAttribute("type", showing ? "password" : "text");
      toggle.setAttribute("aria-pressed", showing ? "false" : "true");
      toggle.textContent = showing ? "Show" : "Hide";
      password.focus();
    });
  }

  var fill = document.getElementById("rl-demo-fill");
  var username = document.getElementById("rl-username");
  if (fill && username && password) {
    fill.addEventListener("click", function () {
      username.value = "cenius@cenius.ai";
      password.value = "cenius";
      username.focus();
    });
  }

  var form = document.querySelector("form[action='/login']");
  var submit = form ? form.querySelector("button[type=submit]") : null;
  if (form && submit) {
    form.addEventListener("submit", function () {
      submit.disabled = true;
      submit.textContent = "Signing in…";
    });
  }
})();
