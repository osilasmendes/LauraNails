setTimeout(() => {
  document.querySelectorAll(".flash").forEach(el => {
    el.style.transition = "opacity .35s ease, transform .35s ease";
    el.style.opacity = "0";
    el.style.transform = "translateY(-8px)";
    setTimeout(() => el.remove(), 400);
  });
}, 4500);
