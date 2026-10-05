"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-location-filters]");
  if (!form) return;
  const district = form.querySelector("[name=district]");
  const block = form.querySelector("[name=block]");
  const feedback = form.querySelector(".filter-feedback");
  let sequence = 0;
  district.addEventListener("change", async () => {
    const current = ++sequence;
    block.replaceChildren(new Option("All blocks", ""));
    feedback.textContent = "";
    if (!district.value) { block.disabled = false; return; }
    block.disabled = true;
    try {
      // Staff option endpoint respects jurisdiction and includes inactive master
      // records for maintenance filters. Public registration uses the public API.
      const response = await fetch("/locations/options/blocks/?district=" + encodeURIComponent(district.value), {headers:{"Accept":"application/json"}});
      if (!response.ok) throw new Error("Unable to load blocks");
      const data = await response.json();
      if (current !== sequence) return;
      for (const item of data.results) block.add(new Option(item.name_en, item.id));
    } catch (error) {
      if (current === sequence) feedback.textContent = "Blocks could not be loaded. Apply the district filter to continue.";
    } finally {
      if (current === sequence) block.disabled = false;
    }
  });
});
